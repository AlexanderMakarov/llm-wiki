"""CLI/integration tests for post-synth end-of-run summary (#113 Slice 2).

Covers ``print_synth_run_summary`` via ``cmd_synthesize`` on a tmp vault.
Synthesis backends are faked — no Claude/Ollama network calls.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki.cli import build_parser, cmd_synthesize


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
