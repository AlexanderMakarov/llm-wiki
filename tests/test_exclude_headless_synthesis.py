"""Tests for the synthesis half of ``filters.exclude_headless`` (#8 follow-up).

``exclude_headless`` used to act only at ingest. That left a hole with a
compounding cost: synthesis shells out to an agent CLI, that call is itself
logged as a session, `sync` ingests it, and the next synthesis pass pays to
summarize the wiki's own output — which produces yet more headless sessions.
Any session converted before the filter shipped (or while it was off) stayed
in the backlog permanently, because nothing downstream could even tell it was
headless: ``raw/`` frontmatter recorded no launch marker at all.

So two things are covered here:

* the converter now persists ``entrypoint`` / ``promptSource`` / ``is_headless``,
  making the classification survive into ``raw/``; and
* the backlog and ``synthesize`` both honour it, so a headless session already
  sitting in ``raw/`` is never synthesized.

The existing ``test_exclude_headless.py`` covers the ingest half — that a
headless session is not converted in the first place.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki._frontmatter import is_headless
from llmwiki.synth.pipeline import (
    DEFAULT_EXCLUDE_HEADLESS,
    resolve_exclude_headless,
)
from llmwiki.convert import DEFAULT_CONFIG
from llmwiki.convert import render_session_markdown
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions
from llmwiki.synth.pipeline import (
    discover_unsynth_session_rels,
    synthesize_new_sessions,
)


# ─── unit: is_headless frontmatter helper ────────────────────────────────


def test_is_headless_true_for_bool():
    assert is_headless({"is_headless": True}) is True


def test_is_headless_true_for_string_true():
    assert is_headless({"is_headless": "true"}) is True


def test_is_headless_false_for_string_false():
    assert is_headless({"is_headless": "false"}) is False


def test_is_headless_falls_back_to_entrypoint():
    # Written before is_headless existed but after the markers were kept.
    assert is_headless({"entrypoint": "sdk-cli"}) is True
    assert is_headless({"entrypoint": "sdk-py"}) is True


def test_is_headless_falls_back_to_prompt_source():
    assert is_headless({"promptSource": "sdk"}) is True


def test_is_headless_false_for_interactive_markers():
    assert is_headless({"entrypoint": "cli", "promptSource": "typed"}) is False


def test_is_headless_false_when_all_markers_absent():
    # Deliberately conservative: a pre-#8 file carries no marker, and
    # guessing from message counts would silently reclassify real sessions
    # as machine noise. Leaving them visible in the backlog is the safer
    # failure. Re-sync (or prune) to classify legacy files.
    assert is_headless({}) is False
    assert is_headless({"project": "proj", "user_messages": 1, "tool_calls": 0}) is False


# ─── unit: policy resolution ─────────────────────────────────────────────


def test_exclude_headless_defaults_to_on():
    assert DEFAULT_EXCLUDE_HEADLESS is True
    assert resolve_exclude_headless({}) is True
    assert resolve_exclude_headless(None) is True


def test_exclude_headless_reads_config():
    assert resolve_exclude_headless({"filters": {"exclude_headless": False}}) is False


def test_exclude_headless_tolerates_string_spellings():
    assert resolve_exclude_headless({"filters": {"exclude_headless": "false"}}) is False
    assert resolve_exclude_headless({"filters": {"exclude_headless": "true"}}) is True


def test_exclude_headless_shares_the_converter_key():
    # One setting governs ingest and backlog, so the two can never disagree
    # about what "headless" means.
    assert DEFAULT_CONFIG["filters"]["exclude_headless"] is True


# ─── converter records the markers into raw/ ─────────────────────────────


def _records(entrypoint: str, prompt_source: str) -> list[dict]:
    return [
        {
            "type": "user",
            "sessionId": "s1",
            "cwd": "/home/u/code/proj",
            "timestamp": "2026-04-16T10:00:00Z",
            "entrypoint": entrypoint,
            "promptSource": prompt_source,
            "message": {"role": "user", "content": "hi"},
        }
    ]


def _render(records: list[dict]) -> str:
    text, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/s1.jsonl"),
        project_slug="proj",
        redact=lambda s: s,
        config={},
        is_subagent_file=False,
    )
    return text


def test_converter_records_headless_markers_in_frontmatter():
    text = _render(_records("sdk-cli", "sdk"))
    assert "entrypoint: sdk-cli" in text
    assert "promptSource: sdk" in text
    assert "is_headless: true" in text


def test_converter_marks_interactive_session_not_headless():
    text = _render(_records("cli", "typed"))
    assert "is_headless: false" in text


def test_converted_headless_frontmatter_round_trips():
    # The whole point: what the converter writes must be readable back by the
    # synthesis policy, or the backlog can't act on it.
    meta, _body = parse_frontmatter(_render(_records("sdk-cli", "sdk")))
    assert is_headless(meta) is True


# ─── backlog: a headless session in raw/ is not eligible ─────────────────


class _P:
    """Cheap Path-ish object for injecting raw_sessions without touching disk."""

    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]
        self.stem = self.name.rsplit(".", 1)[0]

    def __str__(self) -> str:
        return self._rel

    def relative_to(self, other):
        return self


def _mixed_sessions():
    # One real session + one headless `claude -p` run, nothing synthesized.
    return [
        (_P("proj/2026-04-16-real.md"), {"project": "proj"}, "body " * 200),
        (_P("proj/2026-04-16-headless.md"),
         {"project": "proj", "is_headless": True}, "body " * 200),
    ]


def test_estimate_excludes_headless_from_backlog():
    rpt = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(),
        state_keys=set(),
        synthesized_source_keys=set(),
        exclude_headless=True,
    )
    assert rpt["new_sessions"] == 1
    assert rpt["excluded_headless"] == 1
    assert all("headless" not in it["rel"] for it in rpt["unsynth_items"])


def test_estimate_includes_headless_when_filter_disabled():
    rpt = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(),
        state_keys=set(),
        synthesized_source_keys=set(),
        exclude_headless=False,
    )
    assert rpt["new_sessions"] == 2
    assert rpt["excluded_headless"] == 0


def test_estimate_headless_does_not_inflate_full_force_cost():
    # Full-force bills the whole corpus, so an ineligible session must be
    # dropped before costing — not merely omitted from the incremental bucket.
    on = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(), state_keys=set(),
        synthesized_source_keys=set(), exclude_headless=True,
    )
    off = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(), state_keys=set(),
        synthesized_source_keys=set(), exclude_headless=False,
    )
    assert on["full_force_usd"] < off["full_force_usd"]


# ─── synthesize: the run agrees with the estimate ────────────────────────

_REAL = """---
title: "Session: real"
type: source
date: 2026-04-16
source_file: raw/sessions/proj/2026-04-16-real.md
slug: real
project: proj
is_subagent: false
is_headless: false
---

# real

Body of a genuine interactive session.
"""

_HEADLESS = """---
title: "Session: headless"
type: source
date: 2026-04-16
source_file: raw/sessions/proj/2026-04-16-headless.md
slug: headless
project: proj
is_subagent: false
entrypoint: sdk-cli
promptSource: sdk
is_headless: true
---

# headless

Body of an automated `claude -p` run.
"""


def _seed(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-16-real.md").write_text(_REAL, encoding="utf-8")
    (raw / "2026-04-16-headless.md").write_text(_HEADLESS, encoding="utf-8")
    return tmp_path / "raw" / "sessions", tmp_path / "wiki" / "sources"


def _written(wiki_sources: Path) -> list[str]:
    return sorted(p.name for p in wiki_sources.rglob("*.md"))


def test_synthesize_skips_headless_already_in_raw(tmp_path: Path):
    raw, wiki_sources = _seed(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=tmp_path / "state.json", include_docs=False,
        exclude_headless=True,
    )
    assert summary["synthesized"] == 1
    assert all("headless" not in n for n in _written(wiki_sources))


def test_synthesize_skips_headless_even_with_force(tmp_path: Path):
    # --force means "redo synthesis", not "override eligibility" — same
    # contract the include_subagents policy holds to.
    raw, wiki_sources = _seed(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=tmp_path / "state.json", include_docs=False,
        force=True, exclude_headless=True,
    )
    assert summary["synthesized"] == 1
    assert all("headless" not in n for n in _written(wiki_sources))


def test_synthesize_includes_headless_when_filter_disabled(tmp_path: Path):
    raw, wiki_sources = _seed(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=tmp_path / "state.json", include_docs=False,
        exclude_headless=False,
    )
    assert summary["synthesized"] == 2


def test_synthesize_does_not_leave_headless_in_raw(tmp_path: Path):
    # Skipping must not delete: raw/ is immutable, and "not synthesized" is
    # a backlog policy, not a retention one.
    raw, wiki_sources = _seed(tmp_path)
    synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=tmp_path / "state.json", include_docs=False,
        exclude_headless=True,
    )
    assert (raw / "proj" / "2026-04-16-headless.md").is_file()


# ─── the estimate must describe the run exactly ──────────────────────────


def test_estimate_backlog_matches_what_synthesize_runs(tmp_path: Path):
    """`--estimate` and a real run must agree on eligibility.

    The bug this guards: the estimate counted headless sessions as backlog
    and quoted a price for them, while a run would (now) skip them — so the
    number shown was for work that would never happen.
    """
    raw, wiki_sources = _seed(tmp_path)
    state = tmp_path / "state.json"

    predicted = discover_unsynth_session_rels(
        raw_dir=raw, wiki_sources_dir=wiki_sources, state_file=state,
        exclude_headless=True,
    )
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=state, include_docs=False, exclude_headless=True,
    )
    assert len(predicted) == summary["synthesized"]
    assert all("headless" not in rel for rel in predicted)
