"""Tests for ``llmwiki synthesize --estimate`` breakdown (G-07 · #293).

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
from llmwiki.synth.estimate import BODY_CHAR_CAP, DEFAULT_OUTPUT_TOKENS, LEAN_OVERHEAD_TOKENS
from llmwiki.synth.pipeline import _discover_raw_sessions

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
    template_chars = mean_chars - BODY_CHAR_CAP
    rpt = synthesize_estimate_report(
        raw_sessions=[(_P("a.md"), {}, "x" * BODY_CHAR_CAP)],
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
    """claude_cli.py truncates bodies to BODY_CHAR_CAP before sending."""
    capped = [(_P("a.md"), {}, "x" * BODY_CHAR_CAP)]
    way_over = [(_P("a.md"), {}, "x" * (BODY_CHAR_CAP * 10))]
    a = synthesize_estimate_report(raw_sessions=capped, state_keys=set())
    b = synthesize_estimate_report(raw_sessions=way_over, state_keys=set())
    assert a["full_force_usd"] == pytest.approx(b["full_force_usd"])


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
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    # #387 U4: the "Synthesized (history)" row label was confusing; renamed to
    # "Already synthesized" for plainer English.
    for line in ("Corpus:", "Already synthesized:", "New since last run:"):
        assert line in cp.stdout, f"missing `{line}`"


def test_cli_estimate_prints_both_cost_rows(estimate_vault):
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Incremental sync:" in cp.stdout
    assert "Full re-synth:" in cp.stdout


def test_cli_estimate_prints_model_and_per_page_cost(estimate_vault):
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    # Split into its halves so a surprising figure is traceable to either
    # the agent scaffolding or a bloated topic vocabulary.
    assert "Per page:" in cp.stdout
    assert "agent overhead" in cp.stdout
    assert "prompt" in cp.stdout
    assert "Pricing model:" in cp.stdout or "Execution model:" in cp.stdout


def test_cli_estimate_does_not_claim_cache_reuse(estimate_vault):
    """Each page is its own process — there is no prefix to re-read."""
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert "cache write" not in cp.stdout
    assert "hits)" not in cp.stdout


def test_cli_estimate_doesnt_hit_network(estimate_vault):
    """--estimate is a pure-local calculation; no HTTP libs needed."""
    # Run with DNS poisoned (127.0.0.1 only) via env isn't trivial —
    # instead assert that the CLI returns quickly (sub-5s is plenty).
    t0 = time.monotonic()
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    elapsed = time.monotonic() - t0
    assert cp.returncode == 0
    assert elapsed < 30, f"estimate took {elapsed:.1f}s — too slow"


def test_cli_estimate_never_prints_negative_dollar(estimate_vault):
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0
    assert "$-" not in cp.stdout


def test_cli_estimate_full_force_not_less_than_incremental(estimate_vault):
    """Invariant: re-synthesizing everything can't cost less than just
    the new bucket. Cheap regression guard against formula bugs."""
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
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
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Candidates (pre-run state):" in cp.stdout
    # Bare ``Candidates:`` was the pre-#113 forecast-flavoured header.
    assert re.search(r"(?m)^Candidates:\s", cp.stdout) is None


def test_cli_estimate_prints_pending_sources_note(estimate_vault):
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert _PENDING_SOURCES_NOTE in cp.stdout


def test_cli_estimate_does_not_print_post_run_summary(estimate_vault):
    """Estimate-only mode must not emit a completed-synth / post-harvest summary."""
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
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
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert re.search(
        r"Corpus:\s+\d+ eligible sources \(\d+ sessions \+ \d+ docs\)",
        cp.stdout,
    ), cp.stdout


def test_cli_estimate_already_synthesized_uses_of_eligible(estimate_vault):
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
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
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "Source pages (current state):" in cp.stdout
    assert "2 on disk" in cp.stdout
    assert "1 sessions + 1 docs + 0 stubs" in cp.stdout

def test_cli_estimate_does_not_print_pages_in_wiki_sources(estimate_vault):
    """Pre-#81 wording that framed synthesized counts as wiki/sources pages."""
    cp = _run_cli("synthesize", "--estimate", "--vault", str(estimate_vault))
    assert cp.returncode == 0, cp.stderr
    assert "pages in wiki/sources/" not in cp.stdout
