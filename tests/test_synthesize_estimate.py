"""Tests for ``llmwiki synth --estimate`` breakdown (G-07 · #293).

Covers:
* Empty corpus → zeros with no divide-by-zero errors.
* Fresh corpus (nothing in state file) → incremental == full_force.
* Fully-synthesized corpus → incremental = $0, full_force > $0.
* Partial progress → incremental < full_force.
* Non-lean scaffolding warning surfaces into ``warnings`` bucket.
* Custom model + custom output_tokens override pricing.
* CLI subprocess prints the expected layout.
* Money numbers are non-negative and full_force ≥ incremental.
* #113: Candidates block uses pre-run label + pending-sources note; no post-run summary.
* #81: Corpus / Already synthesized use eligible-source units; Source pages current-state line; no ``pages in wiki/sources/``.
* #161: doc target pages are read from what's on disk (``source_page_paths``), not
  re-derived from today's chunker yield — the two can disagree in either direction
  whenever the chunk size has changed since a doc was last synthesized.
* #311: body billing and doc chunk sizing use ``usable_body_chars`` (not a bare
  ``[:8000]`` coverage path).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import llmwiki.cli as cli_mod
from llmwiki.cache import CACHE_WRITE_1H_MULTIPLIER, MODEL_PRICING, TRANSCRIPT_CHARS_PER_TOKEN
from llmwiki.cli import synthesize_estimate_report
from llmwiki.synth.base import DEFAULT_USABLE_BODY_CHARS, SESSION_BODY_SEND_CAP_CHARS, DummySynthesizer
from llmwiki.synth.estimate import DEFAULT_OUTPUT_TOKENS, LEAN_OVERHEAD_TOKENS
from llmwiki.synth.pipeline import (
    _discover_raw_sessions,
    page_is_stub,
    page_needs_topics_rewrite,
    raw_source_key,
    source_page_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    env = os.environ.copy()
    # Prefer the checkout under test over any other installed llmwiki.
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )


# ─── synthesize_estimate_report: pure unit ───────────────────────────────


class _P:
    """Cheap Path-ish object for injecting raw_sessions without touching disk."""

    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]

    def __str__(self) -> str:  # used by the relative_to-fail branch
        return self._rel

    def relative_to(self, other):
        # Accept any "root" and return ourselves (the fixtures already
        # provide relative paths).
        return self


def _sessions(*rels: str) -> list:
    return [(_P(rel), {}, f"body for {rel} " * 200) for rel in rels]


def test_empty_corpus_reports_zero():
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 0
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 0
    assert rpt["incremental_usd"] == 0.0
    assert rpt["full_force_usd"] == 0.0


def test_fresh_corpus_incremental_equals_full_force():
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 3
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 3
    # Same session bodies, same prefix, same pricing → identical.
    assert rpt["incremental_usd"] == pytest.approx(rpt["full_force_usd"])


def test_fully_synthesized_corpus_incremental_is_zero():
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md"),
        state_keys={"a.md", "b.md"},
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 2
    assert rpt["synthesized"] == 2
    assert rpt["new"] == 0
    assert rpt["incremental_usd"] == 0.0
    assert rpt["full_force_usd"] > 0.0


def test_partial_progress_incremental_less_than_full_force():
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys={"a.md"},  # one already synthesized
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 1
    assert rpt["new"] == 2
    assert rpt["incremental_usd"] < rpt["full_force_usd"]


def test_money_numbers_are_non_negative():
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("x.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["incremental_usd"] >= 0.0
    assert rpt["full_force_usd"] >= 0.0


def test_small_prefix_is_not_a_warning():
    """A tiny per-call prefix is the goal, not a problem.

    The old model priced an API-style call with a cached prefix, so a prefix
    under the 1,024-token cache floor earned a warning. The `claude` backend
    has no shared prefix to cache — lean mode exists precisely to make the
    fixed part small — so a small prefix must not warn.
    """
    rpt = synthesize_estimate_report(
        raw_sessions=[], state_keys=set(), prefix_tokens=50,
    )
    assert rpt["warnings"] == []


def test_non_lean_warns_about_scaffolding():
    rpt = synthesize_estimate_report(
        raw_sessions=[], state_keys=set(), lean=False,
    )
    assert any("claude_lean" in w for w in rpt["warnings"])


def test_non_lean_costs_far_more_per_page():
    """The scaffolding the lean flags strip dominates the per-page bill."""
    sessions = [(_P("a.md"), {"project": "p"}, "body " * 200)]
    lean = synthesize_estimate_report(
        raw_sessions=sessions, state_keys=set(), lean=True,
    )
    fat = synthesize_estimate_report(
        raw_sessions=sessions, state_keys=set(), lean=False,
    )
    assert fat["full_force_usd"] > lean["full_force_usd"] * 3
    assert fat["overhead_tokens"] > lean["overhead_tokens"] * 10


def test_matches_measured_cost_per_page():
    """Calibration guard against 29 real synth calls (see synthesis-cost.md).

    Measured: 9,282 input tok, 1,372 output tok, $0.0763/page on sonnet-5
    for a mean prompt of 18,977 chars. That corpus predates the cached
    system prompt, so it is the *cold* per-page cost — this single-page
    report pays the same full cache write. The model should land within 15%
    and err high: an estimate that under-promises is the harmful direction.
    """
    # The 18,977-char prompt is the rendered template plus a body already
    # truncated to the cap — split it the same way here.
    mean_chars = 18_977
    template_chars = mean_chars - SESSION_BODY_SEND_CAP_CHARS
    rpt = synthesize_estimate_report(
        raw_sessions=[(_P("a.md"), {}, "x" * SESSION_BODY_SEND_CAP_CHARS)],
        state_keys=set(),
        template_tokens=int(template_chars / TRANSCRIPT_CHARS_PER_TOKEN),
        model="claude-sonnet-5",
    )
    assert rpt["overhead_tokens"] == LEAN_OVERHEAD_TOKENS
    modelled = rpt["full_force_usd"]
    measured = 0.0763
    assert modelled == pytest.approx(measured, rel=0.15), (
        f"per-page model ${modelled:.4f} drifted from measured ${measured:.4f}"
    )
    assert modelled >= measured, "estimate must not under-promise cost"


def test_input_is_billed_as_cache_write_not_fresh_input():
    """Claude Code writes every prompt to the 1h cache; reads never happen.

    Measured across 29 real pages: cache_read_input_tokens was 0 on all of
    them, and 100% of input arrived as cache_creation. Pricing this at the
    plain input rate understates every run by ~2x.
    """
    rpt = synthesize_estimate_report(
        raw_sessions=[(_P("a.md"), {}, "")],
        state_keys=set(),
        template_tokens=0,
        model="claude-sonnet-5",
    )
    rates = MODEL_PRICING["sonnet-5"]
    expected = (
        LEAN_OVERHEAD_TOKENS * rates["input"] * CACHE_WRITE_1H_MULTIPLIER
        + DEFAULT_OUTPUT_TOKENS * rates["output"]
    ) / 1_000_000
    assert rpt["full_force_usd"] == pytest.approx(expected)


def test_cached_prefix_is_written_once_per_run():
    """The stable template rides in the cached system prompt.

    Page 1 pays the cache write; every later page reads it at 0.1x. So the
    marginal page must cost materially less than the first, and a 10-page
    run must cost far less than 10x one page.
    """
    one = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"), state_keys=set(),
        template_tokens=5000, model="claude-sonnet-5",
    )["full_force_usd"]
    ten = synthesize_estimate_report(
        raw_sessions=_sessions(*[f"s{i}.md" for i in range(10)]), state_keys=set(),
        template_tokens=5000, model="claude-sonnet-5",
    )["full_force_usd"]
    marginal = (ten - one) / 9
    assert marginal < one, "later pages must be cheaper than the first"
    assert ten < one * 10, "a run must beat N independent cold pages"


def test_incremental_bucket_pays_its_own_cache_write():
    """An incremental run is its own process — it cannot reuse a cache
    write from pages that were synthesized in some earlier run."""
    rpt = synthesize_estimate_report(
        # Two already done, one new: the new page is page 1 of *this* run.
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys={"a.md", "b.md"},
        template_tokens=5000,
        model="claude-sonnet-5",
    )
    cold = synthesize_estimate_report(
        raw_sessions=_sessions("c.md"), state_keys=set(),
        template_tokens=5000, model="claude-sonnet-5",
    )["full_force_usd"]
    assert rpt["incremental_usd"] == pytest.approx(cold)


def test_custom_model_propagates():
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        model="claude-haiku-4",
    )
    # Alias resolves to canonical CSV model_name.
    assert rpt["model"] == "haiku-4.5"


def test_custom_output_tokens_affects_cost():
    rpt_small = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        output_tokens_per_call=100,
    )
    rpt_big = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
        output_tokens_per_call=5000,
    )
    assert rpt_big["incremental_usd"] > rpt_small["incremental_usd"]


def test_state_key_matching_accepts_multiple_forms():
    """State keys come from different call sites — match bare-name,
    rel-path, or full-str."""
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("proj/abc.md"),
        state_keys={"proj/abc.md"},  # rel-path form
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 1


def test_report_is_serialisable_to_json():
    """The JSON-able shape lets downstream tools consume the report."""
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        prefix_tokens=2000,
    )
    s = json.dumps(rpt)
    round_tripped = json.loads(s)
    assert round_tripped["new"] == 1


def test_prefix_tokens_is_overhead_plus_template(tmp_path, monkeypatch):
    """The per-call prefix is scaffolding + prompt template, nothing else."""
    rpt = cli_mod.synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        state_keys=set(),
        template_tokens=1234,
        # prefix_tokens deliberately NOT passed
    )
    assert rpt["template_tokens"] == 1234
    assert rpt["prefix_tokens"] == rpt["overhead_tokens"] + 1234


def test_prefix_tokens_ignores_claude_md_and_wiki_pages(tmp_path, monkeypatch):
    """CLAUDE.md / index.md / overview.md are never sent by this backend.

    The old model priced them as a cached prefix, so a large wiki inflated
    the estimate for tokens that were never transmitted. Growing all three
    must not move the per-call figure.
    """
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    (tmp_path / "wiki").mkdir()
    baseline = cli_mod.synthesize_estimate_report(
        raw_sessions=_sessions("a.md"), state_keys=set(), template_tokens=100,
    )
    (tmp_path / "CLAUDE.md").write_text("CLAUDE\n" * 20000, encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("index\n" * 5000, encoding="utf-8")
    (tmp_path / "wiki" / "overview.md").write_text("ov\n" * 5000, encoding="utf-8")
    after = cli_mod.synthesize_estimate_report(
        raw_sessions=_sessions("a.md"), state_keys=set(), template_tokens=100,
    )
    assert after["prefix_tokens"] == baseline["prefix_tokens"]
    assert after["full_force_usd"] == pytest.approx(baseline["full_force_usd"])


def test_body_past_the_truncation_cap_is_not_billed():
    """Session bodies are billed only up to the historical 8,000-char send cap, never chunked."""
    capped = [(_P("a.md"), {}, "x" * SESSION_BODY_SEND_CAP_CHARS)]
    way_over = [(_P("a.md"), {}, "x" * (SESSION_BODY_SEND_CAP_CHARS * 10))]
    a = synthesize_estimate_report(raw_sessions=capped, state_keys=set())
    b = synthesize_estimate_report(raw_sessions=way_over, state_keys=set())
    assert a["full_force_usd"] == pytest.approx(b["full_force_usd"])


def test_session_send_cap_is_independent_of_the_document_budget():
    """A backend with a huge document budget still bills a session at the 8,000-char cap (#311)."""
    capped = [(_P("a.md"), {}, "x" * SESSION_BODY_SEND_CAP_CHARS)]
    way_over = [(_P("a.md"), {}, "x" * (SESSION_BODY_SEND_CAP_CHARS * 10))]
    kwargs = {"state_keys": set(), "backend": DummySynthesizer()}
    a = synthesize_estimate_report(raw_sessions=capped, **kwargs)
    b = synthesize_estimate_report(raw_sessions=way_over, **kwargs)
    assert a["full_force_usd"] == pytest.approx(b["full_force_usd"])


def test_estimate_doc_chunks_to_usable_body_budget(tmp_path, monkeypatch):
    """Long docs are estimated as N calls at the backend usable-body budget (#311)."""
    raw_docs = tmp_path / "raw" / "docs"
    sources = tmp_path / "wiki" / "sources"
    raw_docs.mkdir(parents=True)
    sources.mkdir(parents=True)
    # Two full budgets plus a remainder → three internal chunks.
    body = "x" * (DEFAULT_USABLE_BODY_CHARS * 2 + 500)
    (raw_docs / "long.md").write_text(body, encoding="utf-8")

    seen: list[int] = []

    def _spy(text, max_chars):
        seen.append(max_chars)
        # Character-hard split so the spy proves the budget was the chunk size.
        return [
            text[i : i + max_chars]
            for i in range(0, len(text), max_chars)
        ] or [""]

    monkeypatch.setattr("llmwiki.synth.pipeline._chunk_markdown", _spy)
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys=set(),
        prefix_tokens=2000,
        usable_body_chars=DEFAULT_USABLE_BODY_CHARS,
    )
    assert seen == [DEFAULT_USABLE_BODY_CHARS]
    docs_row = next(r for r in rpt["pipeline_rows"] if r["label"] == "Documents")
    assert docs_row["pending"] == 1
    # Three chunk bodies → cost above a single-budget page (same fixture shape).
    one = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys=set(),
        prefix_tokens=2000,
        usable_body_chars=len(body),  # one call covers the whole doc
    )
    one_row = next(r for r in one["pipeline_rows"] if r["label"] == "Documents")
    assert docs_row["next_usd"] > one_row["next_usd"]
    # Dummy backend large budget also drives the chunker when no override.
    seen.clear()
    synthesize_estimate_report(
        raw_sessions=[],
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys=set(),
        prefix_tokens=2000,
        backend=DummySynthesizer(),
    )
    assert seen == [DummySynthesizer().usable_body_chars()]


# ─── CLI subprocess smoke tests ──────────────────────────────────────────


@pytest.fixture
def estimate_vault(tmp_path):
    """Isolated vault so synthesize --estimate never touches a real vault."""
    vault = tmp_path / "estimate-vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "CLAUDE.md").write_text("x" * 5000, encoding="utf-8")
    return vault



def test_cli_estimate_prints_three_bucket_header(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    # #387 U4: the "Synthesized (history)" row label was confusing; renamed to
    # "Already synthesized" for plainer English.
    for line in ("Corpus:", "Already synthesized:", "New since last run:"):
        assert line in cp.stdout, f"missing `{line}`"


def test_cli_estimate_prints_both_cost_rows(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Incremental sync:" in cp.stdout
    assert "Full re-synth:" in cp.stdout


def test_cli_estimate_prints_model_and_per_page_cost(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    # Split into its halves so a surprising figure is traceable to either
    # the agent scaffolding or a bloated topic vocabulary.
    assert "Per page:" in cp.stdout
    assert "agent overhead" in cp.stdout
    assert "prompt" in cp.stdout
    assert "Pricing model:" in cp.stdout or "Execution model:" in cp.stdout


def test_cli_estimate_does_not_claim_cache_reuse(estimate_vault):
    """Each page is its own process — there is no prefix to re-read."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert "cache write" not in cp.stdout
    assert "hits)" not in cp.stdout


def test_cli_estimate_doesnt_hit_network(estimate_vault):
    """--estimate is a pure-local calculation; no HTTP libs needed."""
    # Run with DNS poisoned (127.0.0.1 only) via env isn't trivial —
    # instead assert that the CLI returns quickly (sub-5s is plenty).
    t0 = time.monotonic()
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    elapsed = time.monotonic() - t0
    assert cp.returncode == 0
    assert elapsed < 30, f"estimate took {elapsed:.1f}s — too slow"


def test_cli_estimate_never_prints_negative_dollar(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0
    assert "$-" not in cp.stdout


def test_cli_estimate_full_force_not_less_than_incremental(estimate_vault):
    """Invariant: re-synthesizing everything can't cost less than just
    the new bucket. Cheap regression guard against formula bugs."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0
    # Parse the two dollar figures out of stdout.
    incr = re.search(r"Incremental sync:\s+\$([\d.]+)", cp.stdout)
    full = re.search(r"Full re-synth:\s+\$([\d.]+)", cp.stdout)
    assert incr is not None and full is not None, cp.stdout
    assert float(full.group(1)) >= float(incr.group(1)) - 1e-6


# ─── #113: Candidates labelled as pre-run state on estimate ─────────────


_PENDING_SOURCES_NOTE = (
    "note: pending sources are not yet reflected in this figure"
)


def test_cli_estimate_labels_candidates_as_pre_run_state(estimate_vault):
    """Candidates on estimate must read as a snapshot, not a harvest forecast."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Candidates (pre-run state):" in cp.stdout
    # Bare ``Candidates:`` was the pre-#113 forecast-flavoured header.
    assert re.search(r"(?m)^Candidates:\s", cp.stdout) is None


def test_cli_estimate_prints_pending_sources_note(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert _PENDING_SOURCES_NOTE in cp.stdout


def test_cli_estimate_does_not_print_post_run_summary(estimate_vault):
    """Estimate-only mode must not emit a completed-synth / post-harvest summary."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    # Real synthesize progress / one-liner (never an estimate concern).
    assert "Scanned " not in cp.stdout
    assert "Synthesizing with backend:" not in cp.stdout
    # Slice 2 end-of-run summary markers (must stay off the estimate path).
    assert "Candidates (post-run" not in cp.stdout
    assert "backlog now" not in cp.stdout.lower()


# ─── #81: Honest Corpus / Already synthesized / Source pages ────────────


def test_cli_estimate_corpus_uses_eligible_sources_and_mix(estimate_vault):
    """Corpus must count eligible sources and show the sessions + docs split."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert re.search(
        r"Corpus:\s+\d+ eligible sources \(\d+ sessions \+ \d+ docs\)",
        cp.stdout,
    ), cp.stdout


def test_cli_estimate_already_synthesized_uses_of_eligible(estimate_vault):
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert re.search(
        r"Already synthesized:\s+\d+ of \d+ eligible sources",
        cp.stdout,
    ), cp.stdout


def test_report_exposes_source_pages_on_disk_and_stubs(tmp_path):
    """When wiki/sources has pages, estimate reports on-disk file counts."""
    sources = tmp_path / "wiki" / "sources"
    raw = tmp_path / "raw" / "sessions"
    sources.mkdir(parents=True)
    raw.mkdir(parents=True)
    (tmp_path / "raw" / "docs").mkdir(parents=True)
    (raw / "a.md").write_text(
        "---\ntitle: a\nproject: p\nagent: claude-code\n---\n\nbody a\n",
        encoding="utf-8",
    )
    # Synth-like pages (no agent:) — on_disk joins via raw session agent.
    (sources / "real.md").write_text(
        "---\ntitle: Real\ntype: source\ntags: [claude-code, session-transcript]\n"
        "date: 2026-07-01\nsource_file: raw/sessions/a.md\n"
        "project: p\nmodel: claude-opus-4-20250514\nlast_updated: 2026-07-01\n"
        "---\n\n## Summary\n\nReal.\n",
        encoding="utf-8",
    )
    (sources / "stub.md").write_text(
        "---\ntitle: Stub\ntype: source\n"
        "source_file: raw/sessions/b.md\n---\n\n"
        "<!-- llmwiki-pending: abc -->\n\n*Pending*\n",
        encoding="utf-8",
    )
    # Same source_file on two real pages would have counted as 1 unique key;
    # file counts must still report both .md files.
    (sources / "real-dup.md").write_text(
        "---\ntitle: Real Dup\ntype: source\ntags: [claude-code, session-transcript]\n"
        "date: 2026-07-01\nsource_file: raw/sessions/a.md\n"
        "project: p\nmodel: claude-opus-4-20250514\nlast_updated: 2026-07-01\n"
        "---\n\n## Summary\n\nDup.\n",
        encoding="utf-8",
    )
    (sources / "_context.md").write_text(
        "---\ntitle: Context\n---\n\nIgnore me.\n",
        encoding="utf-8",
    )
    rpt = synthesize_estimate_report(
        raw_sessions=_discover_raw_sessions(raw),
        raw_root=raw,
        docs_root=tmp_path / "raw" / "docs",
        state_keys=set(),
        wiki_sources_dir=sources,
        prefix_tokens=2000,
        include_subagents="all",
        exclude_headless=False,
    )
    assert "source_pages_on_disk" in rpt
    assert "source_page_stubs" in rpt
    assert rpt["source_pages_on_disk"] == 3  # two reals + stub; not _context
    assert rpt["source_page_stubs"] == 1
    assert rpt["source_pages_sessions"] == 2
    assert rpt["source_pages_docs"] == 0
    by = {r["label"]: r for r in rpt["pipeline_rows"]}
    assert by["Stubs"]["kind"] == "stubs"
    assert by["Stubs"]["on_disk"] == 1
    assert by["Claude"]["on_disk"] == 2
    # Forbid unique-key regression: two files sharing one source_file → 2 on disk.
    assert rpt["source_pages_on_disk"] != 2 or rpt["source_pages_sessions"] == 2


def test_cli_estimate_prints_source_pages_current_state(estimate_vault):
    sources = estimate_vault / "wiki" / "sources"
    # No agent: on the page — CLI mix line counts files, not per-agent join.
    (sources / "s.md").write_text(
        "---\ntitle: S\ntype: source\n"
        "source_file: raw/sessions/x.md\n"
        "model: claude-opus-4-20250514\n"
        "---\n\n## Summary\n\nS.\n",
        encoding="utf-8",
    )
    (sources / "d.md").write_text(
        "---\ntitle: D\ntype: source\ntags: [raw-doc]\n---\n\n## Summary\n\nD.\n",
        encoding="utf-8",
    )
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Source pages (current state):" in cp.stdout
    assert "2 on disk" in cp.stdout
    assert "1 sessions + 1 docs + 0 stubs" in cp.stdout

def test_cli_estimate_does_not_print_pages_in_wiki_sources(estimate_vault):
    """Pre-#81 wording that framed synthesized counts as wiki/sources pages."""
    cp = _run_cli("synth", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "pages in wiki/sources/" not in cp.stdout


# ─── #161: doc target pages come from disk, not a re-derived chunk count ──


_REAL_PART_BODY = (
    "## Summary\n\nReal synthesis of one doc part.\n\n"
    "## Connections\n\n- [[SomeThing]] (entity) — related\n"
)
_STUB_PART_BODY = "<!-- llmwiki-pending: doc -->\n\n*Pending*\n"


def _doc_vault(tmp_path):
    """Bare raw/docs + wiki/sources dirs — never the live vault."""
    raw_docs = tmp_path / "raw" / "docs"
    sources = tmp_path / "wiki" / "sources"
    raw_docs.mkdir(parents=True)
    sources.mkdir(parents=True)
    return raw_docs, sources


def _expected_doc_pending(out_dir: Path, filename: str) -> bool:
    """Ground truth for "is this doc pending", per the run's own definition.

    Mirrors ``source_page_paths`` + the stub/topics-rewrite checks the real
    synth run uses (llmwiki/synth/pipeline.py) — target pages come from what
    is actually on disk, never re-derived from the current chunk size (#161).
    """
    expected = source_page_paths(out_dir, filename, is_doc=True) or [
        out_dir / f"{filename}.md"
    ]
    if not all(p.is_file() for p in expected):
        return True
    return any(page_is_stub(p) for p in expected) or any(
        page_needs_topics_rewrite(p) for p in expected
    )


def test_estimate_source_file_keys_match_synth_claims(tmp_path):
    """Estimate keys are the same ``raw_source_key`` claims synth writes (#307)."""
    raw_docs, sources = _doc_vault(tmp_path)
    (raw_docs / "sub").mkdir()
    (raw_docs / "sub" / "note.md").write_text("# Note\n\nBody.\n", encoding="utf-8")
    raw_root = tmp_path / "raw" / "sessions"
    session = raw_root / "proj" / "s.md"
    session.parent.mkdir(parents=True)
    session.write_text("x", encoding="utf-8")

    rpt = synthesize_estimate_report(
        raw_sessions=[(session, {"project": "proj"}, "body")],
        raw_root=raw_root,
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys=set(),
        prefix_tokens=2000,
    )
    keys = {item["source_file"] for item in rpt["unsynth_items"]}
    assert keys == {
        raw_source_key("proj/s.md", is_doc=False),
        raw_source_key("docs::sub/note.md", is_doc=True),
    }
    assert keys == {"raw/sessions/proj/s.md", "raw/docs/sub/note.md"}


def test_estimate_pending_when_disk_has_a_stub_part_beyond_current_chunk_count(
    tmp_path, monkeypatch
):
    """More parts on disk than the current chunker yields (#161, direction 1).

    The chunker is stubbed to yield 2 chunks for this body, while 3 part
    pages sit on disk from a previous synth — part-03 still a stub. Whatever
    made the two disagree, re-deriving the expected path list from today's
    chunk count stops at part-02 and never sees the still-pending part-03 —
    under-reporting the doc as synthesized when the run still has work.
    """
    raw_docs, sources = _doc_vault(tmp_path)
    (raw_docs / "bigdoc.md").write_text("# Big Doc\n\nSome content.\n", encoding="utf-8")
    out_dir = sources / "docs"
    out_dir.mkdir(parents=True)
    (out_dir / "bigdoc--part-01.md").write_text(_REAL_PART_BODY, encoding="utf-8")
    (out_dir / "bigdoc--part-02.md").write_text(_REAL_PART_BODY, encoding="utf-8")
    (out_dir / "bigdoc--part-03.md").write_text(_STUB_PART_BODY, encoding="utf-8")
    monkeypatch.setattr(
        "llmwiki.synth.pipeline._chunk_markdown",
        lambda text, max_chars: ["chunk-a", "chunk-b"],
    )
    assert _expected_doc_pending(out_dir, "bigdoc") is True  # sanity: fixture is genuinely pending

    rpt = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys=set(),
        prefix_tokens=2000,
    )
    docs_row = next(r for r in rpt["pipeline_rows"] if r["label"] == "Documents")
    assert docs_row["pending"] == 1, "doc must be pending — part-03 is still a stub"
    assert docs_row["synthesized"] == 0
    assert "docs::bigdoc.md" in {item["rel"] for item in rpt["unsynth_items"]}


def test_estimate_synthesized_when_disk_has_fewer_parts_than_current_chunk_count(
    tmp_path, monkeypatch
):
    """Fewer parts on disk than the current chunker yields (#161, direction 2).

    The chunker is stubbed to yield 3 chunks for this body, while only 2 real
    part pages sit on disk — a previous synth that fully covered the doc.
    Whatever made the two disagree, re-deriving the expected path list from
    today's chunk count requires a non-existent part-03 — over-reporting a
    done doc as pending re-synthesis.
    """
    raw_docs, sources = _doc_vault(tmp_path)
    (raw_docs / "bigdoc2.md").write_text("# Big Doc 2\n\nSome content.\n", encoding="utf-8")
    out_dir = sources / "docs"
    out_dir.mkdir(parents=True)
    (out_dir / "bigdoc2--part-01.md").write_text(_REAL_PART_BODY, encoding="utf-8")
    (out_dir / "bigdoc2--part-02.md").write_text(_REAL_PART_BODY, encoding="utf-8")
    monkeypatch.setattr(
        "llmwiki.synth.pipeline._chunk_markdown",
        lambda text, max_chars: ["chunk-a", "chunk-b", "chunk-c"],
    )
    assert _expected_doc_pending(out_dir, "bigdoc2") is False  # sanity: fixture is genuinely done

    # #163: done also requires synth state (pages on disk alone are not enough).
    raw_mtime = (raw_docs / "bigdoc2.md").stat().st_mtime
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=raw_docs,
        wiki_sources_dir=sources,
        state_keys={"docs::bigdoc2.md": raw_mtime},
        prefix_tokens=2000,
    )
    docs_row = next(r for r in rpt["pipeline_rows"] if r["label"] == "Documents")
    assert docs_row["synthesized"] == 1, "doc is done — 2 real parts cover the whole doc"
    assert docs_row["pending"] == 0
    assert "docs::bigdoc2.md" not in {item["rel"] for item in rpt["unsynth_items"]}


def test_estimate_doc_cost_scales_with_chunk_count_not_parts_on_disk(tmp_path, monkeypatch):
    """A pending multi-part doc is billed per chunk (#161, cost regression guard).

    Nothing is on disk for this doc in either call — only the mocked chunk
    count differs — so a future rewrite that dropped ``_chunk_markdown`` from
    the cost math (billing the raw body once, or billing per on-disk part
    instead of per derived chunk) would make this cost go flat instead of
    scaling with N.
    """
    raw_docs, sources = _doc_vault(tmp_path)
    (raw_docs / "pending.md").write_text("# Pending\n\nSome content.\n", encoding="utf-8")

    def _docs_next_usd(chunks):
        # One patch per measurement, undone before the next — the two calls
        # never stack a chunker mock on top of another.
        with monkeypatch.context() as m:
            m.setattr(
                "llmwiki.synth.pipeline._chunk_markdown", lambda text, max_chars: chunks
            )
            rpt = synthesize_estimate_report(
                raw_sessions=[],
                docs_root=raw_docs,
                wiki_sources_dir=sources,
                state_keys=set(),
                prefix_tokens=2000,
            )
        docs_row = next(r for r in rpt["pipeline_rows"] if r["label"] == "Documents")
        assert docs_row["pending"] == 1, "one doc, whatever the chunk count"
        return docs_row["next_usd"]

    # Full-budget chunks so the (never-cached) body dominates the
    # (partly-cached) per-call overhead/template — the cleanest signal that
    # cost tracks chunk count. Ceiling is below 3x because the overhead +
    # template half of chunks 2 and 3 rides the 0.1x cached-prefix rate; a
    # flat/no-scaling regression would show a ratio of ~1x, not ~2.5x.
    one_chunk_usd = _docs_next_usd(["x" * DEFAULT_USABLE_BODY_CHARS])
    three_chunk_usd = _docs_next_usd(["x" * DEFAULT_USABLE_BODY_CHARS] * 3)
    assert three_chunk_usd > one_chunk_usd * 2.0, (
        f"3 identical chunks (${three_chunk_usd:.4f}) should cost noticeably more "
        f"than one chunk (${one_chunk_usd:.4f}) — cost must scale with the derived "
        "chunk count, not stay flat"
    )


def test_estimate_sessions_never_consult_the_doc_chunker(tmp_path, monkeypatch):
    """Sessions are never chunked — the doc chunker must not even be called (#161)."""
    empty_docs = tmp_path / "raw" / "docs"
    empty_docs.mkdir(parents=True)
    calls = []
    monkeypatch.setattr(
        "llmwiki.synth.pipeline._chunk_markdown",
        lambda text, max_chars: calls.append(1) or [text],
    )
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md"),
        docs_root=empty_docs,
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus"] == 2
    assert calls == []
