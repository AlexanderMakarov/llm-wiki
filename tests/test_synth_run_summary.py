"""CLI/integration tests for the synth run summary lines.

Covers ``print_synth_run_summary`` via ``cmd_synthesize`` on a tmp vault
(#113 Slice 2) and ``print_synth_run_start`` — the batch-size line printed
before the first page result — via ``synthesize_new_sessions`` (#118).
Synthesis backends are faked — no Claude/Ollama network calls.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions


def _mk_vault(tmp_path: Path, links: dict[str, list[str]] | None = None) -> Path:
    """Minimal vault; optional wiki/sources wikilinks for harvestable backlog."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    sources = vault / "wiki" / "sources"
    sources.mkdir(parents=True)
    for slug, names in (links or {}).items():
        body = "\n".join(f"- [[{n}]]" for n in names)
        (sources / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\ntype: source\n---\n\n## Connections\n{body}\n",
            encoding="utf-8",
        )
    return vault


def _ok_synth_summary(*, synthesized: int = 2) -> dict:
    return {
        "total_scanned": synthesized,
        "new_files": synthesized,
        "synthesized": synthesized,
        "skipped": 0,
        "errors": [],
    }


def _interrupted_synth_summary(*, synthesized: int = 1) -> dict:
    return {
        "total_scanned": synthesized,
        "new_files": synthesized,
        "synthesized": synthesized,
        "skipped": 0,
        "errors": [],
        "interrupted": True,
    }


class _ClassifyBackend:
    """Available stub that classifies harvested names (no network)."""

    name = "stub"

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:
        return "Recurring: entity\n"


_SYNTHESIZED_LINE = re.compile(r"(?m)^Synthesized:\s+(\d+)\s*$")
_DURATION_LINE = re.compile(r"(?m)^Duration:\s+(\d+\.\d+)s\s*$")
_TOKENS_LINE = re.compile(r"(?m)^Tokens:")
_COST_LINE = re.compile(r"(?m)^Cost:")


def test_synth_prints_post_harvest_run_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Default ``synth`` ends with count + duration; Candidates stays on harvest line only."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(
        ["synth", "--vault", str(vault), "--min-refs", "3"]
    )

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_ok_synth_summary(synthesized=2),
        ),
    ):
        rb.return_value = _ClassifyBackend()
        rc = cmd_synthesize(args)

    assert rc == 0
    out = capsys.readouterr().out
    m_syn = _SYNTHESIZED_LINE.search(out)
    m_dur = _DURATION_LINE.search(out)
    assert m_syn is not None, out
    assert m_syn.group(1) == "2"
    assert m_dur is not None, out
    assert float(m_dur.group(1)) >= 0.0
    # Harvest owns Candidates — do not duplicate in the end summary.
    assert "Candidates (post-run" not in out
    assert "backlog now" not in out.lower()
    assert "Candidates:" in out  # harvest line
    assert out.count("Candidates:") == 1


def test_synth_run_summary_omits_fabricated_token_and_cost(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unknown usage — summary must not invent Tokens/Cost lines."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(["synth", "--vault", str(vault)])

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_ok_synth_summary(synthesized=1),
        ),
    ):
        rb.return_value = _ClassifyBackend()
        assert cmd_synthesize(args) == 0

    out = capsys.readouterr().out
    assert _SYNTHESIZED_LINE.search(out) is not None
    assert _DURATION_LINE.search(out) is not None
    assert _TOKENS_LINE.search(out) is None, out
    assert _COST_LINE.search(out) is None, out


def test_synth_sources_only_omits_candidates_from_end_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--sources-only`` prints count + duration and skips harvest Candidates."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(
        ["synth", "--sources-only", "--vault", str(vault)]
    )

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_ok_synth_summary(synthesized=3),
        ) as synth,
        patch("llmwiki.cli.run_harvest") as harvest,
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)

    assert rc == 0
    synth.assert_called_once()
    harvest.assert_not_called()
    out = capsys.readouterr().out
    assert _SYNTHESIZED_LINE.search(out) is not None
    assert _SYNTHESIZED_LINE.search(out).group(1) == "3"
    assert _DURATION_LINE.search(out) is not None
    assert "Candidates (post-run" not in out
    assert "backlog now" not in out.lower()
    assert _TOKENS_LINE.search(out) is None
    assert _COST_LINE.search(out) is None


def test_interrupted_synth_harvests_then_exits_130(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Default ``synth`` on interrupt: harvest written sources, exit 130."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(["synth", "--vault", str(vault)])

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_interrupted_synth_summary(synthesized=1),
        ),
        patch("llmwiki.cli.run_harvest", return_value=0) as harvest,
        patch("llmwiki.cli._refresh_review_counts"),
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)

    assert rc == 130
    harvest.assert_called_once()
    assert harvest.call_args.kwargs.get("require_sources") is False
    out = capsys.readouterr().out
    assert "Pending names collected from written sources." in out


def test_interrupted_synth_harvest_failure_prints_retry_not_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Interrupt still exits 130; harvest failure must not claim success."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(["synth", "--vault", str(vault)])

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_interrupted_synth_summary(synthesized=1),
        ),
        patch("llmwiki.cli.run_harvest", return_value=2) as harvest,
        patch("llmwiki.cli._refresh_review_counts") as refresh,
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)

    assert rc == 130
    harvest.assert_called_once()
    refresh.assert_not_called()
    captured = capsys.readouterr()
    assert "Pending names collected from written sources." not in captured.out
    assert "Harvest after interrupt failed" in captured.err
    assert "llmwiki synth --candidates-only" in captured.out


def test_interrupted_sources_only_prints_candidates_only_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--sources-only`` on interrupt: no harvest; print the one-line command."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    args = build_parser().parse_args(
        ["synth", "--sources-only", "--vault", str(vault)]
    )

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch(
            "llmwiki.cli.synthesize_new_sessions",
            return_value=_interrupted_synth_summary(synthesized=1),
        ),
        patch("llmwiki.cli.run_harvest") as harvest,
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)

    assert rc == 130
    harvest.assert_not_called()
    out = capsys.readouterr().out
    assert "llmwiki synth --candidates-only" in out.splitlines()


def test_estimate_skips_end_of_run_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--estimate`` must never emit the completed-synth post-run summary."""
    vault = _mk_vault(tmp_path)
    args = build_parser().parse_args(
        ["synth", "--estimate", "--vault", str(vault)]
    )

    with patch("llmwiki.cli.synthesize_new_sessions") as synth:
        rc = cmd_synthesize(args)

    assert rc == 0
    synth.assert_not_called()
    out = capsys.readouterr().out
    assert _SYNTHESIZED_LINE.search(out) is None, out
    assert _DURATION_LINE.search(out) is None, out
    assert "Candidates (post-run" not in out
    assert "backlog now" not in out.lower()
    # Pre-run Candidates block is still allowed on estimate.
    assert "Candidates (pre-run state):" in out


# ─── start-of-run batch count (#118 Slice 1) ─────────────────────────────

_START_LINE = re.compile(r"(?m)^Synthesizing (\d+) source\(s\) with (\S+) \((\d+) at a time\)$")
_NOTHING_LINE = "Nothing to synthesize — every source is already up to date."
_PAGE_LINE = re.compile(r"(?m)^  \[\d+/\d+\] synthesized: ")

_DOC = """---
title: "{slug} notes"
slug: {slug}
---

# {slug}

Synthetic fixture body for the start-of-run count tests.
"""

_CLAIMING_PAGE = """---
title: "Hand-written notes"
type: source
tags: [manual]
source_file: raw/docs/{slug}.md
project: manual
---

## Summary

A real page with link data, filed outside the derived slug scheme.

## Connections

- [[Synthesis]] — the pipeline that would otherwise duplicate this page
"""


def _seed_docs(vault: Path, slugs: tuple[str, ...]) -> None:
    """Write one synthetic raw doc per slug into ``<vault>/raw/docs``."""
    for slug in slugs:
        (vault / "raw" / "docs" / f"{slug}.md").write_text(
            _DOC.format(slug=slug), encoding="utf-8"
        )


def _claim_source(vault: Path, slug: str) -> None:
    """Add a real source page claiming ``raw/docs/<slug>.md`` (dedup guard)."""
    page = vault / "wiki" / "sources" / "manual" / f"{slug}-notes.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_CLAIMING_PAGE.format(slug=slug), encoding="utf-8")


def _run_synth(vault: Path, *, dry_run: bool = False) -> dict:
    """Run the real pipeline against a tmp vault on the dummy backend."""
    return synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        log_path=vault / "wiki" / "log.md",
        state_file=vault / "state.json",
        dry_run=dry_run,
    )


def test_run_start_line_precedes_first_page_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The batch size is announced before any page result trickles in."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    assert _run_synth(vault)["synthesized"] == 2

    out = capsys.readouterr().out
    start = _START_LINE.search(out)
    first_page = _PAGE_LINE.search(out)
    assert start is not None, out
    assert first_page is not None, out
    assert start.start() < first_page.start(), out


def test_run_start_count_matches_queue_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The announced count equals the number of sources actually queued."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    summary = _run_synth(vault)

    out = capsys.readouterr().out
    start = _START_LINE.search(out)
    assert start is not None, out
    assert int(start.group(1)) == summary["new_files"] == 3
    assert start.group(2) == DummySynthesizer().name


def test_run_start_count_excludes_dedup_skipped_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A source dropped by the dedup guard is not counted in the batch.

    The guard runs while the queue is still being built, so its
    ``skipped:`` line legitimately prints before the start line — what
    matters is that the announced count covers only real work.
    """
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))
    _claim_source(vault, "gamma")

    summary = _run_synth(vault)

    out = capsys.readouterr().out
    start = _START_LINE.search(out)
    assert start is not None, out
    assert summary["skipped"] == 1
    assert int(start.group(1)) == summary["new_files"] == 2
    assert out.count("not duplicating)") == 1
    assert len(_PAGE_LINE.findall(out)) == 2


def test_empty_queue_reports_nothing_to_synthesize(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An up-to-date corpus says so plainly instead of announcing zero."""
    vault = _mk_vault(tmp_path)

    summary = _run_synth(vault)

    out = capsys.readouterr().out
    assert summary["new_files"] == 0
    assert _NOTHING_LINE in out
    assert _START_LINE.search(out) is None, out


def test_dry_run_omits_run_start_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--dry-run`` keeps its own preview line and adds no start line."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    summary = _run_synth(vault, dry_run=True)

    out = capsys.readouterr().out
    assert summary["synthesized"] == 0
    assert f"[dry-run] Would synthesize 2 new sources using {DummySynthesizer().name}" in out
    assert _START_LINE.search(out) is None, out
    assert _NOTHING_LINE not in out
