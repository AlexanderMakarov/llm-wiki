"""Whole-feature acceptance tests for #147 / #145: one synthesis pass per source.

# @layer: integration
# @spec: 009-one-call-per-source-synth
# @regression

Slices 1–7 each carry unit/integration coverage for their own change; this file
verifies the feature as a whole against functional-spec.md. Tests that would
only re-assert a slice module are omitted — the matrix points at them instead.

AC coverage matrix (FR<n>-AC<m>, functional-spec.md bullet order):

    FR1-AC1  → test_full_loop_dummy_synth_harvest_promote_shared_thing   [headline]
    FR1-AC2  → covered by tests/test_synth_pipeline.py
               ::test_llm_synth_runs_prepare_known_names_once_before_pages
               (frozen vocab prefix carries SharedTopic into every job-2 prompt)
    FR1-AC3  → test_fr1_empty_topics_still_summarise_without_inventing_names
    FR1-neg  → test_fr1_invalid_kind_is_not_classified_and_needs_rewrite
    FR2-AC1  → covered by tests/test_synth_pipeline.py
               ::test_connections_only_page_queued_for_topics_rewrite
    FR2-AC2  → covered by tests/test_synth_pipeline.py
               ::test_parseable_kind_page_skipped_when_mtime_current
    FR3-AC1  → test_full_loop_dummy_synth_harvest_promote_shared_thing
               (+ tests/test_candidates_harvest.py
               ::test_run_harvest_writes_stub_from_topic_bullets_with_backend_none)
    FR3-AC2  → test_full_loop_dummy_synth_harvest_promote_shared_thing
    FR3-AC3  → covered by tests/test_candidates_harvest.py
               ::test_run_harvest_succeeds_when_backend_is_none
               ::test_run_harvest_succeeds_without_probing_the_backend
    FR3-neg  → covered by tests/test_candidates_harvest.py
               ::test_run_harvest_does_not_call_classify_names
    FR4-AC1  → test_full_loop_dummy_synth_harvest_promote_shared_thing
               (+ tests/test_candidates.py::test_promote_succeeds_without_llm_backend)
    FR4-AC2  → covered by tests/test_candidates.py
               ::test_promote_preserves_nonempty_key_facts
    FR4-AC3  → test_fr4_promote_never_calls_synthesize_key_facts_or_mention_clip
               (+ tests/test_candidates.py
               ::test_promote_does_not_call_synthesize_or_mention_helpers)
    FR5-AC1  → covered by tests/test_synth_pipeline.py
               ::test_llm_synth_runs_prepare_known_names_once_before_pages
    FR5-AC2  → covered by tests/test_topics.py
               ::test_prepare_known_names_calls_llm_once_and_caches
    FR5-AC3  → covered by FR5-AC1 (job 1 re-runs on next synthesize_new_sessions)
    FR5-AC4  → covered by tests/test_synth_parallel.py
               ::test_an_interrupt_records_the_pages_that_reached_disk
    FR5-AC5  → covered by tests/test_synth_pipeline.py
               ::test_dummy_synth_does_not_call_job1_prepare_known_names
               (+ tests/test_topics.py
               ::test_prepare_known_names_skips_non_llm_backend)
    FR6-AC1  → covered by tests/test_synth_run_summary.py
               ::test_interrupted_synth_harvests_then_exits_130
               ::test_interrupted_sources_only_prints_candidates_only_hint
    FR6-AC2  → covered by tests/test_synth_parallel.py
               ::test_an_interrupt_records_the_pages_that_reached_disk
    FR6-AC3  → covered by tests/test_state_widget.py
               ::test_build_refreshes_pipeline_on_disk_mismatch
               ::test_build_skips_pipeline_refresh_when_on_disk_matches
    FR7-AC1  → covered by tests/test_reference_coverage.py (retired heading in cli.md)
               + tests/e2e/test_cli_smoke.py::test_consolidate_topics_is_retired
    FR7-AC2  → covered by tests/e2e/test_cli_smoke.py
               ::test_consolidate_topics_is_retired
    FR7-AC3  → test_fr10_agent_kit_matches_offline_promote_and_no_consolidate
    FR8-AC1  → test_full_loop_dummy_synth_harvest_promote_shared_thing
    FR8-AC2  → test_fr8_description_not_rewritten_when_more_facts_arrive
    FR8-AC3  → out of scope (#148); merge still concatenates — no LLM rewrite added
    FR9-AC1  → covered by tests/test_synth_run_summary.py
               ::test_run_start_line_precedes_first_page_line
    FR9-AC2  → covered by tests/test_synth_run_summary.py interrupt tests +
               tests/test_synth_parallel.py interrupt drain
    FR9-AC3  → covered by tests/test_synth_parallel.py
               ::test_one_failing_source_does_not_stop_the_batch
    FR10-AC1 → test_fr10_changelog_unreleased_describes_offline_promote_and_retirement
    FR10-AC2 → covered by docs (asserted via CHANGELOG + agent-kit greps;
               cli.md current-tense checked indirectly by reference coverage)
    FR10-AC3 → test_fr10_agent_kit_matches_offline_promote_and_no_consolidate

Notes on RED validation (implementation already landed on this branch):

    Prefer asserting against ``git show origin/main:<path>`` that the old
    contracts existed. A test GREEN on this worktree is valid when it would be
    RED on origin/main — documented per test.

    Verified on origin/main before writing this file:
    - ``llmwiki/candidates.py`` raised ``KeyFactsBackendError`` from promote
      and called ``synthesize_key_facts`` when evidence existed without an LLM.
    - ``llmwiki/candidates_harvest.py`` called ``classify_names`` on the default
      harvest path.
    - ``llmwiki/synth/pipeline.py`` re-raised ``KeyboardInterrupt`` after drain.
    - ``llmwiki/cli.py`` ``cmd_consolidate_topics`` wrote a prompt / accepted
      ``--complete``.
    - ``llmwiki/agent_kit/commands/wiki-candidates.md`` told agents promote
      **fails** on unset/dummy backend; ``wiki-synth.md`` told agents to run
      ``consolidate-topics``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import candidates as candidates_mod
from llmwiki.candidates import promote
from llmwiki.candidates_harvest import run_harvest
from llmwiki.source_topics import parse_source_topics, source_page_needs_topics_rewrite
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions

# ─── helpers ───────────────────────────────────────────────────────────────


def _git_show_main(relpath: str) -> str:
    """Return ``origin/main`` blob for ``relpath``, or empty if unavailable."""
    result = subprocess.run(
        ["git", "show", f"origin/main:{relpath}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _seed_shared_thing_raw(tmp_path: Path, *, n: int = 3) -> Path:
    """N raw sessions under project ``shared-thing`` so Dummy emits ``[[SharedThing]]``.

    Stock ``DummySynthesizer`` (G-12) only puts the project entity in Connections.
    Title-casing ``shared-thing`` yields ``SharedThing`` with kind + nested fact —
    enough for harvest at the default min_refs=3.
    """
    raw = tmp_path / "raw" / "sessions" / "shared-thing"
    raw.mkdir(parents=True)
    for i in range(n):
        stem = f"session-{i}"
        (raw / f"2026-04-1{i}-{stem}.md").write_text(
            f"---\n"
            f'title: "Session: {stem}"\n'
            f"slug: {stem}\n"
            f"project: shared-thing\n"
            f"date: 2026-04-1{i}\n"
            f"model: claude-sonnet-4-6\n"
            f"user_messages: 1\n"
            f"tool_calls: 0\n"
            f"---\n\n"
            f"# {stem}\n\n"
            f"Discussed [[SharedThing]] in this session.\n",
            encoding="utf-8",
        )
    return tmp_path / "raw" / "sessions"


def _mk_wiki_scaffold(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return ``(wiki_dir, wiki_sources, log_path)`` under ``tmp_path``."""
    wiki = tmp_path / "wiki"
    sources = wiki / "sources"
    sources.mkdir(parents=True)
    log = wiki / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    return wiki, sources, log


def _write_topic_source(
    wiki: Path,
    slug: str,
    *,
    name: str,
    kind: str,
    description: str,
    facts: list[str],
) -> Path:
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fact_lines = "\n".join(f"  - fact: {f}" for f in facts)
    path.write_text(
        f"---\ntitle: {slug}\ntype: source\n---\n\n"
        f"## Connections\n"
        f"- [[{name}]] ({kind}) — {description}\n"
        f"{fact_lines}\n",
        encoding="utf-8",
    )
    return path


# ─── FR1+FR3+FR4 headline — full offline loop ─────────────────────────────


def test_full_loop_dummy_synth_harvest_promote_shared_thing(tmp_path: Path) -> None:
    """FR1+FR3+FR4: Dummy synth → harvest kind/facts/desc → promote with None.

    One end-to-end path no single slice file walks: three queued sources all
    surface ``[[SharedThing]]`` with parseable bullets, harvest writes a stub
    carrying kind + facts + description with ``backend=None``, and promote
    with ``synthesizer=None`` moves it retaining those facts.

    RED on origin/main: harvest called ``classify_names``; promote raised
    ``KeyFactsBackendError`` without an LLM (``git show origin/main:…``).
    """
    # @regression
    raw = _seed_shared_thing_raw(tmp_path, n=3)
    wiki, sources, log = _mk_wiki_scaffold(tmp_path)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        wiki_sources_dir=sources,
        log_path=log,
        state_file=tmp_path / "state.json",
    )
    assert summary["synthesized"] == 3, summary.get("errors")
    assert summary.get("interrupted") is not True

    written_pages = list(sources.rglob("*.md"))
    assert len(written_pages) == 3
    for page in written_pages:
        body = page.read_text(encoding="utf-8")
        topics = parse_source_topics(body)
        assert any(t.name == "SharedThing" and t.kind == "entity" for t in topics), (
            f"expected SharedThing (entity) topic bullets in {page}"
        )
        assert "## Key Claims" in body
        assert "## Key Quotes" in body

    rc = run_harvest(wiki, backend=None)
    assert rc == 0
    stub = wiki / "candidates" / "entities" / "SharedThing.md"
    assert stub.is_file()
    stub_text = stub.read_text(encoding="utf-8")
    assert "type: entity" in stub_text
    assert "status: candidate" in stub_text
    assert "parent project" in stub_text  # description from Dummy bullet
    assert "Session covered project `shared-thing`" in stub_text

    promoted = promote("SharedThing", wiki, synthesizer=None)
    assert promoted == wiki / "entities" / "SharedThing.md"
    assert promoted.is_file()
    assert not stub.exists()
    promoted_text = promoted.read_text(encoding="utf-8")
    assert "status: reviewed" in promoted_text
    assert "Session covered project `shared-thing`" in promoted_text
    assert "parent project" in promoted_text


# ─── FR1 negatives / empty topics ─────────────────────────────────────────


def test_fr1_invalid_kind_is_not_classified_and_needs_rewrite() -> None:
    """FR1 negative: ``(tool)`` is not a usable kind — rewrite still needed.

    ``parse_source_topics`` yields ``kind=None``; harvest must not treat the
    parenthetical as a classified kind. RED vs a naive ``(word)`` grabber.
    """
    # @regression
    body = (
        "## Connections\n"
        "- [[Widget]] (tool) — looks like a kind but is not\n"
        "  - fact: Should not classify as tool.\n"
    )
    records = parse_source_topics(body)
    assert len(records) == 1
    assert records[0].name == "Widget"
    assert records[0].kind is None
    assert source_page_needs_topics_rewrite(body) is True


def test_fr1_empty_topics_still_summarise_without_inventing_names() -> None:
    """FR1-AC3: a source with nothing to file still gets a summary, no fake topics."""
    # @regression
    meta = {
        "slug": "quiet",
        "project": "unknown",
        "date": "2026-04-09",
        "model": "claude-sonnet-4-6",
        "user_messages": 0,
        "tool_calls": 0,
    }
    body = DummySynthesizer().synthesize_source_page(
        "Nothing worth filing.\n", meta, prompt_template=""
    )
    assert "## Summary" in body
    assert parse_source_topics(body) == []
    assert source_page_needs_topics_rewrite(body) is False
    assert "[[SharedThing]]" not in body
    assert re.search(r"- \[\[.+\]\]", body) is None


# ─── FR4 negative — promote never LLM / mention-clip ──────────────────────


class _ExplodingKeyFactsBackend(DummySynthesizer):
    """Would fail loudly if promote still asked an LLM for Key Facts."""

    is_llm = True
    name = "explode-key-facts"

    def synthesize_key_facts(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("promote must not call synthesize_key_facts")

    def synthesize_source_page(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("promote must not call synthesize_source_page")


def test_fr4_promote_never_calls_synthesize_key_facts_or_mention_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR4-AC3 / FR4 negative: promote is offline bookkeeping only.

    RED on origin/main: ``promote`` → ``fill_key_facts_from_evidence`` →
    ``synthesize_key_facts`` / ``KeyFactsBackendError`` when no LLM backend
    (``git show origin/main:llmwiki/candidates.py``).
    """
    # @regression
    wiki = tmp_path / "wiki"
    (wiki / "candidates" / "entities").mkdir(parents=True)
    for slug in ("a", "b", "c"):
        _write_topic_source(
            wiki,
            slug,
            name="Gadget",
            kind="entity",
            description="A small tool",
            facts=[f"Fact from {slug}"],
        )
    (wiki / "candidates" / "entities" / "Gadget.md").write_text(
        '---\ntitle: "Gadget"\ntype: entity\nstatus: candidate\n'
        "sources: [a, b, c]\n---\n\n"
        "# Gadget\n\nA small tool\n\n## Key Facts\n\n"
        "## Connections\n\n- [[a]]\n- [[b]]\n- [[c]]\n",
        encoding="utf-8",
    )

    calls: dict[str, int] = {"mention": 0, "digest": 0}

    def _boom_mention(*_a, **_k):
        calls["mention"] += 1
        raise AssertionError("promote must not call _mention_lines")

    def _boom_digest(*_a, **_k):
        calls["digest"] += 1
        raise AssertionError("promote must not build an LLM evidence digest")

    monkeypatch.setattr(candidates_mod, "_mention_lines", _boom_mention)
    monkeypatch.setattr(candidates_mod, "_evidence_digest", _boom_digest)

    # Even an is_llm backend is ignored: promote deletes synthesizer (#147).
    text = promote(
        "Gadget", wiki, synthesizer=_ExplodingKeyFactsBackend()
    ).read_text(encoding="utf-8")
    assert "Fact from a" in text
    assert "Invented" not in text
    assert calls["mention"] == 0
    assert calls["digest"] == 0

    # Documented RED: old promote path required an LLM for empty Key Facts.
    old = _git_show_main("llmwiki/candidates.py")
    if old:
        assert "KeyFactsBackendError" in old
        assert "synthesize_key_facts" in old


# ─── FR8 — description not rebuilt from fact count ─────────────────────────


def test_fr8_description_not_rewritten_when_more_facts_arrive(tmp_path: Path) -> None:
    """FR8-AC2: opening description stays put when more facts land on re-harvest."""
    # @regression
    wiki = tmp_path / "wiki"
    for slug in ("a", "b", "c"):
        _write_topic_source(
            wiki,
            slug,
            name="Stable",
            kind="concept",
            description="Original short description",
            facts=["First fact"],
        )
    assert run_harvest(wiki, backend=DummySynthesizer()) == 0
    stub = wiki / "candidates" / "concepts" / "Stable.md"
    assert stub.is_file()
    assert "Original short description" in stub.read_text(encoding="utf-8")

    _write_topic_source(
        wiki,
        "d",
        name="Stable",
        kind="concept",
        description="SHOULD NOT REPLACE the opening paragraph",
        facts=["Second fact from later source"],
    )
    assert run_harvest(wiki, backend=None) == 0
    text = stub.read_text(encoding="utf-8")
    assert "Original short description" in text
    assert "SHOULD NOT REPLACE the opening paragraph" not in text
    # Evidence list refreshes; description above Connections does not.
    assert "[[d]]" in text


# ─── FR5 spy (whole-feature call counts) — cite if identical; keep one here? ─
# Covered by test_synth_pipeline.py::test_llm_synth_runs_prepare_known_names_once_before_pages.
# Do not duplicate.


# ─── FR10 — docs / agent kit current tense ─────────────────────────────────


def test_fr10_agent_kit_matches_offline_promote_and_no_consolidate() -> None:
    """FR7-AC3 / FR10-AC3: agent kit must not teach dummy-fail promote or consolidate.

    RED on origin/main: wiki-candidates said promote **fails** on dummy;
    wiki-synth instructed ``consolidate-topics`` (``git show origin/main:…``).
    """
    # @regression
    candidates_cmd = (
        REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-candidates.md"
    ).read_text(encoding="utf-8")
    synth_cmd = (
        REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-synth.md"
    ).read_text(encoding="utf-8")

    # Must not claim promote fails when backend is dummy/unset (pre-#147 wording).
    assert "Promote **fails**" not in candidates_cmd
    assert "fails** (exit 2" not in candidates_cmd
    assert (
        "no language model required for promote" in candidates_cmd.lower()
        or "Works with Dummy" in candidates_cmd
    )

    assert "llmwiki consolidate-topics" not in synth_cmd or "retired" in synth_cmd.lower()
    assert "Do **not** run `llmwiki consolidate-topics`" in synth_cmd

    old_candidates = _git_show_main("llmwiki/agent_kit/commands/wiki-candidates.md")
    if old_candidates:
        assert "Promote **fails**" in old_candidates or "fails** (exit 2" in old_candidates


def test_fr10_changelog_unreleased_describes_offline_promote_and_retirement() -> None:
    """FR10-AC1: Unreleased notes promote-without-LLM and consolidate-topics gone."""
    # @regression
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = text.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    lowered = unreleased.lower()
    assert "#147" in unreleased or "147" in unreleased
    assert "#145" in unreleased or "145" in unreleased
    assert "consolidate-topics" in lowered
    assert "retired" in lowered or "gone" in lowered
    assert "promote" in lowered
    assert (
        "dummy" in lowered
        or "no language model" in lowered
        or "offline" in lowered
        or "none" in lowered
    )


def test_fr10_source_prompt_keeps_key_claims_and_quotes() -> None:
    """Job 2 prompt still asks for Key Claims / Key Quotes (unchanged in #147)."""
    # @regression
    prompt = (
        REPO_ROOT / "llmwiki" / "synth" / "prompts" / "source_page.md"
    ).read_text(encoding="utf-8")
    assert "## Key Claims" in prompt
    assert "## Key Quotes" in prompt
    assert "(entity)" in prompt
    assert "fact:" in prompt


# ─── FR7 CLI retirement (lightweight; full path in e2e smoke) ──────────────


def test_fr7_consolidate_topics_exits_2_and_complete_writes_nothing(
    tmp_path: Path,
) -> None:
    """FR7-AC2: retired command exits 2; ``--complete`` does not write cache.

    Full CLI smoke lives in ``tests/e2e/test_cli_smoke.py``; this keeps the
    whole-feature suite self-contained without a live vault.
    """
    # @regression
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw").mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    basic = subprocess.run(
        [sys.executable, "-m", "llmwiki", "consolidate-topics", "--vault", str(vault)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert basic.returncode == 2
    combined = (basic.stderr + basic.stdout).lower()
    assert "retired" in combined or "gone" in combined
    assert not (vault / "wiki" / ".llmwiki-topics.json").is_file()
    assert not (vault / "wiki" / ".llmwiki-topic-consolidation.md").is_file()

    reply = tmp_path / "reply.json"
    reply.write_text('{"topics": [], "dropped": []}', encoding="utf-8")
    complete = subprocess.run(
        [
            sys.executable,
            "-m",
            "llmwiki",
            "consolidate-topics",
            "--complete",
            str(reply),
            "--vault",
            str(vault),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert complete.returncode == 2
    assert not (vault / "wiki" / ".llmwiki-topics.json").is_file()


# ─── Documented RED probe (historical contracts on origin/main) ─────────────


def test_red_origin_main_had_four_call_world_contracts() -> None:
    """Documented RED: origin/main still has the pre-#147 four-call contracts.

    Does not execute old code — asserts the historical source strings that
    this branch removed or retired. Skips soft-fail if origin/main is missing.
    """
    # @regression
    harvest = _git_show_main("llmwiki/candidates_harvest.py")
    candidates = _git_show_main("llmwiki/candidates.py")
    pipeline = _git_show_main("llmwiki/synth/pipeline.py")
    cli = _git_show_main("llmwiki/cli.py")
    if not (harvest and candidates and pipeline and cli):
        pytest.skip("origin/main blobs unavailable for RED documentation")

    assert "classify_names(pending" in harvest or "kinds = classify_names" in harvest
    assert "KeyFactsBackendError" in candidates
    assert "synthesize_key_facts" in candidates
    # Old interrupt path re-raised after drain.
    assert "KeyboardInterrupt" in pipeline
    assert "cmd_consolidate_topics" in cli
    assert "--complete" in cli
