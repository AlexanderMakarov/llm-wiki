"""Whole-feature acceptance tests for #81: Honest already-synthesized counts.

# @layer: integration
# @spec: 006-honest-synthesized-counts
# @regression

Maps every acceptance criterion in functional-spec.md to at least one test.
Tests in test_synthesize_estimate.py and test_state_widget.py already cover
several ACs; this file fills the gaps specifically noted in the task:

    AC 2.1.1  → test_ac_211_corpus_session_doc_split_in_report         [unit]
    AC 2.1.1  → test_ac_211_cli_corpus_eligible_phrase_with_mix        [integration]
    AC 2.1.2  → documented as covered by test_synthesize_estimate.py
                ::test_cli_estimate_corpus_uses_eligible_sources_and_mix
    AC 2.2.1  → test_ac_221_already_synthesized_n_of_m_in_report       [unit]
    AC 2.2.2  → documented as covered by test_synthesize_estimate.py
                ::test_cli_estimate_does_not_print_pages_in_wiki_sources
    AC 2.3.1  → test_ac_231_print_source_pages_output_format           [unit]
    AC 2.3.1  → test_ac_231_print_source_pages_says_current_state      [unit]
    AC 2.3.2  → test_ac_232_stale_bookkeeping_gap_visible_in_output    [integration]
    AC 2.3.3  → test_ac_233_source_pages_line_is_not_a_forecast        [unit]
    AC 2.4.1  → documented as covered by test_state_widget.py
                ::test_state_widget_js_has_pipeline_table_and_collapsibles
    AC 2.4.2  → test_ac_242_chunked_doc_counts_as_one_in_pipeline      [unit]
    AC 2.4.3  → documented as covered by test_state_widget.py
                ::test_state_widget_js_on_disk_column_no_under_table_note

Notes on RED:
    Tests referencing already-landed slice tests were RED at implementation
    time; see test_synthesize_estimate.py header.

    New tests in this file exercise scenarios not present in earlier slice
    tests: the stale-bookkeeping divergence case (AC 2.3.2), direct-function
    output format (AC 2.3.1/2.3.3), the corpus split at the unit level
    (AC 2.1.1), and the multi-chunk doc counting as 1 input (AC 2.4.2).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki.state_store import mtime_to_iso
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import _DOC_CHUNK_MAX_CHARS, _chunk_markdown
from llmwiki.synth.reporting import print_source_pages_current_state

REPO_ROOT = Path(__file__).resolve().parents[1]


# ─── helpers ─────────────────────────────────────────────────────────────────


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
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


class _FakePath:
    """Cheap Path-ish stand-in for injecting sessions without touching disk."""

    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]
        self.stem = self.name.removesuffix(".md")

    def __str__(self) -> str:
        return self._rel

    def relative_to(self, other):
        return self


def _sessions(*rels: str) -> list:
    return [(_FakePath(rel), {}, f"body for {rel} " * 200) for rel in rels]


# ─── AC 2.1.1 — corpus_sessions / corpus_docs split in report dict ───────────


def test_ac_211_corpus_session_doc_split_in_report(tmp_path: Path) -> None:
    """AC 2.1.1: report dict exposes corpus_sessions and corpus_docs separately.

    The eligible-source mix (S sessions + D docs) must be available as
    structured data so callers can render it.  The sum must equal corpus.
    """
    # @regression
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text(
        "---\ntitle: Note\nproject: docs\n---\n\ndoc body\n",
        encoding="utf-8",
    )
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md"),
        docs_root=docs,
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus_sessions"] == 2
    assert rpt["corpus_docs"] == 1
    assert rpt["corpus"] == rpt["corpus_sessions"] + rpt["corpus_docs"]


def test_ac_211_corpus_sessions_only_when_no_docs(tmp_path: Path) -> None:
    """AC 2.1.1 (negative): corpus_docs is 0 when raw/docs/ is empty."""
    # @regression
    empty_docs = tmp_path / "no-docs"
    empty_docs.mkdir()
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md"),
        docs_root=empty_docs,
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus_sessions"] == 1
    assert rpt["corpus_docs"] == 0
    assert rpt["corpus"] == 1


# ─── AC 2.2.1 — already-synthesized N of M eligible sources (unit) ───────────


def test_ac_221_already_synthesized_n_of_m_in_report() -> None:
    """AC 2.2.1: synthesized ≤ corpus and M equals the corpus total."""
    # @regression
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md", "c.md"),
        state_keys={"a.md", "b.md"},
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 2
    assert rpt["corpus"] == 3
    # M (the "of M" denominator) must equal corpus — not pages under wiki/sources.
    assert rpt["synthesized"] <= rpt["corpus"]


def test_ac_221_fully_synthesized_still_reports_corpus_m() -> None:
    """AC 2.2.1: when all inputs are synthesized, N of M both equal corpus."""
    # @regression
    rpt = synthesize_estimate_report(
        raw_sessions=_sessions("a.md", "b.md"),
        state_keys={"a.md", "b.md"},
        prefix_tokens=2000,
    )
    assert rpt["synthesized"] == 2
    assert rpt["corpus"] == 2


# ─── AC 2.3.1 — print_source_pages_current_state output format ───────────────


def test_ac_231_print_source_pages_output_format(capsys: pytest.CaptureFixture) -> None:
    """AC 2.3.1: print_source_pages_current_state emits file mix on disk."""
    # @regression
    print_source_pages_current_state(
        pages_on_disk=7, sessions=4, docs=1, stubs=2
    )
    out = capsys.readouterr().out
    assert "Source pages (current state):" in out
    assert "7 on disk" in out
    assert "4 sessions + 1 docs + 2 stubs" in out


def test_ac_231_print_source_pages_zero_stubs(capsys: pytest.CaptureFixture) -> None:
    """AC 2.3.1 (negative): zero stubs is reported — not omitted or hidden."""
    # @regression
    print_source_pages_current_state(
        pages_on_disk=3, sessions=2, docs=1, stubs=0
    )
    out = capsys.readouterr().out
    assert "3 on disk" in out
    assert "2 sessions + 1 docs + 0 stubs" in out


# ─── AC 2.3.3 — Source pages line is current state, not a forecast ───────────


def test_ac_233_source_pages_line_is_not_a_forecast(capsys: pytest.CaptureFixture) -> None:
    """AC 2.3.3: Source pages line must not read as a write forecast.

    The line must carry 'current state' (snapshot language) and must not
    imply the number is the count the upcoming run *will* write.
    """
    # @regression
    print_source_pages_current_state(
        pages_on_disk=5, sessions=3, docs=1, stubs=1
    )
    out = capsys.readouterr().out
    assert "current state" in out
    # Words that would make this read as a run-output prediction.
    for forecast_word in ("will write", "will produce", "to write", "forecast"):
        assert forecast_word not in out.lower(), (
            f"Forecast word '{forecast_word}' must not appear in Source pages line.\n"
            f"Got: {out!r}"
        )


# ─── AC 2.3.2 — stale bookkeeping: divergence between synthesized and on-disk ─


@pytest.fixture
def stale_vault(tmp_path: Path) -> Path:
    """Vault where state claims 2 sources synthesized, but only 1 page on disk.

    Simulates the case where pages were manually deleted after an earlier
    synthesis run — stale bookkeeping.
    """
    vault = tmp_path / "stale-vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    sources = vault / "wiki" / "sources"
    sources.mkdir(parents=True)

    # Two session files — both will appear in the raw corpus.
    for slug in (
        "2026-01-01T10-00-project-alpha",
        "2026-01-02T11-00-project-beta",
    ):
        (sessions / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\nslug: {slug}\nproject: project\n---\n\nBody.\n",
            encoding="utf-8",
        )

    # State marks BOTH sessions synthesized (keys are session-root rels; mtimes
    # must be ≥ raw file mtimes so #163's shared done predicate agrees).
    alpha_rel = "2026-01-01T10-00-project-alpha.md"
    beta_rel = "2026-01-02T11-00-project-beta.md"
    alpha_mtime = (sessions / alpha_rel).stat().st_mtime
    beta_mtime = (sessions / beta_rel).stat().st_mtime
    state = {
        "queue": {"items": [], "legacy_pending_paths": []},
        "sync": {"files": {}, "meta": {}, "counters": {}},
        "synth": {
            "files": {
                alpha_rel: mtime_to_iso(alpha_mtime),
                beta_rel: mtime_to_iso(beta_mtime),
            },
            "pending": [],
            "pending_total": 0,
            "pending_updated_at": "2026-01-03T00:00:00Z",
            "estimate": {},
        },
        "quarantine": {"entries": []},
        "ops": {
            "last_queue_run_at": "",
            "last_lint_run_at": "",
            "last_reflect_run_at": "",
        },
        "meta": {"schema_version": 1, "updated_at": "", "revision": 1},
    }
    (vault / "llmwiki-state.json").write_text(
        json.dumps(state) + "\n", encoding="utf-8"
    )

    # Only ONE page remains on disk (the other was "manually deleted").
    (sources / "project-alpha.md").write_text(
        "---\ntitle: Alpha\ntype: source\n"
        "source_file: raw/sessions/2026-01-01T10-00-project-alpha.md\n---\n\n"
        "## Summary\n\nAlpha page.\n",
        encoding="utf-8",
    )
    return vault


def test_ac_232_stale_bookkeeping_gap_visible_in_output(
    stale_vault: Path,
) -> None:
    """AC 2.3.2: stale state → already-synthesized count > source pages on disk.

    Both numbers must appear with their own correct labels so the gap is
    visible.  The already-synthesized count comes from the eligibility
    bookkeeping (inputs) — the source-pages count from disk.  They may
    legitimately differ, and neither may be silently corrected to match the
    other.
    """
    # @regression
    cp = _run_cli("synth", "--estimate", "--vault", str(stale_vault))
    assert cp.returncode == 0, cp.stderr

    # Already synthesized line: eligible-source unit.
    assert re.search(
        r"Already synthesized:\s+\d+ of \d+ eligible sources",
        cp.stdout,
    ), cp.stdout

    # Source pages line: on-disk file count with category mix.
    assert "Source pages (current state):" in cp.stdout, cp.stdout
    assert "on disk" in cp.stdout
    assert "sessions +" in cp.stdout
    assert "docs +" in cp.stdout
    assert "stubs" in cp.stdout

    # Extract the two counts and confirm they are different (divergence visible).
    synth_match = re.search(r"Already synthesized:\s+(\d+) of", cp.stdout)
    pages_match = re.search(r"Source pages \(current state\):\s+(\d+) on disk", cp.stdout)
    assert synth_match is not None, f"Cannot parse Already synthesized line.\nstdout:\n{cp.stdout}"
    assert pages_match is not None, f"Cannot parse Source pages line.\nstdout:\n{cp.stdout}"

    synthesized_count = int(synth_match.group(1))
    pages_on_disk = int(pages_match.group(1))

    # The stale vault has 2 done in state but 1 page on disk.
    assert synthesized_count == 2, (
        f"Expected state to claim 2 synthesized; got {synthesized_count}.\nstdout:\n{cp.stdout}"
    )
    assert pages_on_disk == 1, (
        f"Expected 1 page on disk; got {pages_on_disk}.\nstdout:\n{cp.stdout}"
    )
    assert synthesized_count != pages_on_disk, (
        "Stale vault should show divergence between synthesized inputs and on-disk pages."
    )


def test_ac_232_stale_bookkeeping_no_pages_in_wiki_sources_phrase(
    stale_vault: Path,
) -> None:
    """AC 2.3.2 (negative): stale vault output must not use 'pages in wiki/sources/'."""
    # @regression
    cp = _run_cli("synth", "--estimate", "--vault", str(stale_vault))
    assert cp.returncode == 0, cp.stderr
    assert "pages in wiki/sources/" not in cp.stdout, (
        "Forbidden phrase 'pages in wiki/sources/' found in stale-vault output.\n"
        f"stdout:\n{cp.stdout}"
    )


# ─── AC 2.4.2 — chunked doc counts as 1 input in pipeline table ──────────────


def test_ac_242_chunked_doc_counts_as_one_in_pipeline(tmp_path: Path) -> None:
    """AC 2.4.2: a document that is split into multiple parts is still 1 input.

    The pipeline table tracks eligible inputs, not wiki pages produced.  An
    oversized document generates N wiki source-page files (one per chunk) but
    contributes exactly 1 to the raw/pending/synthesized cell in the pipeline
    row — fan-out is not expanded into the counts.
    """
    # @regression
    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True)
    wiki = tmp_path / "wiki" / "sources"
    wiki.mkdir(parents=True)

    # Write a doc body large enough to produce multiple chunks.
    # _DOC_CHUNK_MAX_CHARS is the actual chunking threshold; exceed it.
    big_body = "# Section A\n\n" + "x " * (_DOC_CHUNK_MAX_CHARS // 2 + 1) + "\n"
    big_body += "# Section B\n\n" + "y " * (_DOC_CHUNK_MAX_CHARS // 2 + 1) + "\n"
    (docs / "big.md").write_text(
        "---\ntitle: Big Doc\nproject: docs\n---\n\n" + big_body,
        encoding="utf-8",
    )

    rpt = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=docs,
        wiki_sources_dir=wiki,
        state_keys=set(),
        prefix_tokens=2000,
    )

    # The document produces more than 1 chunk — verify that.
    chunks = _chunk_markdown(big_body, _DOC_CHUNK_MAX_CHARS)
    assert len(chunks) > 1, "Fixture must produce multiple chunks for this test to be meaningful."

    # Regardless of chunk count, the corpus counts the doc as 1 input.
    assert rpt["corpus_docs"] == 1, (
        f"Expected 1 doc input; got corpus_docs={rpt['corpus_docs']}."
    )
    assert rpt["corpus"] == 1

    # Pipeline rows: Documents row must have raw=1, not raw=len(chunks).
    docs_rows = [r for r in rpt["pipeline_rows"] if r["kind"] == "docs"]
    assert docs_rows, "Expected a Documents row in pipeline_rows."
    docs_row = docs_rows[0]
    assert docs_row["raw"] == 1, (
        f"Expected Documents raw=1; got {docs_row['raw']}. "
        f"(Doc produces {len(chunks)} chunks but is 1 eligible input.)"
    )
    assert docs_row["pending"] == 1


def test_ac_242_single_chunk_doc_also_counts_as_one(tmp_path: Path) -> None:
    """AC 2.4.2 (baseline): a single-chunk doc also counts as exactly 1 input."""
    # @regression
    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True)
    wiki = tmp_path / "wiki" / "sources"
    wiki.mkdir(parents=True)
    (docs / "small.md").write_text(
        "---\ntitle: Small\nproject: docs\n---\n\nShort body.\n",
        encoding="utf-8",
    )
    rpt = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=docs,
        wiki_sources_dir=wiki,
        state_keys=set(),
        prefix_tokens=2000,
    )
    assert rpt["corpus_docs"] == 1
    docs_rows = [r for r in rpt["pipeline_rows"] if r["kind"] == "docs"]
    assert docs_rows
    assert docs_rows[0]["raw"] == 1


# ─── AC coverage summary (cross-reference) ───────────────────────────────────
#
# AC 2.1.1  → test_ac_211_corpus_session_doc_split_in_report            (this file)
# AC 2.1.1  → test_ac_211_corpus_sessions_only_when_no_docs             (this file)
# AC 2.1.1  → tests/test_synthesize_estimate.py::test_cli_estimate_corpus_uses_eligible_sources_and_mix
# AC 2.1.2  → tests/test_synthesize_estimate.py::test_cli_estimate_does_not_print_pages_in_wiki_sources
# AC 2.2.1  → test_ac_221_already_synthesized_n_of_m_in_report          (this file)
# AC 2.2.1  → test_ac_221_fully_synthesized_still_reports_corpus_m      (this file)
# AC 2.2.1  → tests/test_synthesize_estimate.py::test_cli_estimate_already_synthesized_uses_of_eligible
# AC 2.2.2  → tests/test_synthesize_estimate.py::test_cli_estimate_does_not_print_pages_in_wiki_sources
# AC 2.3.1  → test_ac_231_print_source_pages_output_format              (this file)
# AC 2.3.1  → test_ac_231_print_source_pages_zero_stubs                 (this file)
# AC 2.3.1  → tests/test_synthesize_estimate.py::test_cli_estimate_prints_source_pages_current_state
# AC 2.3.2  → test_ac_232_stale_bookkeeping_gap_visible_in_output       (this file)
# AC 2.3.2  → test_ac_232_stale_bookkeeping_no_pages_in_wiki_sources_phrase (this file)
# AC 2.3.3  → test_ac_233_source_pages_line_is_not_a_forecast           (this file)
# AC 2.4.1  → tests/test_state_widget.py::test_state_widget_js_has_pipeline_table_and_collapsibles
# AC 2.4.2  → test_ac_242_chunked_doc_counts_as_one_in_pipeline         (this file)
# AC 2.4.2  → test_ac_242_single_chunk_doc_also_counts_as_one           (this file)
# AC 2.4.3  → tests/test_state_widget.py::test_state_widget_js_on_disk_column_no_under_table_note
