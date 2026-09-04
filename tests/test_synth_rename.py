"""Tests for ``llmwiki synth`` harvest defaults (#90)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llmwiki.cli import build_parser, cmd_synthesize


def test_synth_subcommand_registered() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None))
    assert "synth" in sub.choices


def test_synth_check_wires_cmd_synthesize() -> None:
    args = build_parser().parse_args(["synth", "--check"])
    assert args.func is cmd_synthesize


def test_sources_only_and_candidates_only_mutex() -> None:
    parser = build_parser()
    try:
        parser.parse_args(["synth", "--sources-only", "--candidates-only"])
        raised = False
    except SystemExit:
        raised = True
    assert raised


def test_synth_default_runs_harvest_after_sources(tmp_path) -> None:
    """Bare ``synth`` (not --sources-only) must harvest after synthesizing (#90)."""
    vault = tmp_path / "vault"
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True)
    args = build_parser().parse_args(["synth", "--vault", str(vault)])

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch("llmwiki.cli.synthesize_new_sessions") as synth,
        patch("llmwiki.cli.run_harvest", return_value=0) as harvest,
        patch("llmwiki.cli._refresh_review_counts") as refresh,
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        synth.return_value = {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [],
        }
        rc = cmd_synthesize(args)

    assert rc == 0
    harvest.assert_called_once()
    assert harvest.call_args.kwargs.get("require_sources") is False
    refresh.assert_called_once()


def test_synth_sources_only_skips_harvest(tmp_path) -> None:
    vault = tmp_path / "vault"
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True)
    args = build_parser().parse_args(
        ["synth", "--sources-only", "--vault", str(vault)]
    )

    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch("llmwiki.cli.synthesize_new_sessions") as synth,
        patch("llmwiki.cli.run_harvest") as harvest,
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        synth.return_value = {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [],
        }
        rc = cmd_synthesize(args)

    assert rc == 0
    harvest.assert_not_called()
