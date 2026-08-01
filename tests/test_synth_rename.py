"""Tests for ``llmwiki synth`` rename + synthesize deprecation (#90 PR 3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llmwiki.cli import build_parser, cmd_synthesize


def test_synth_subcommand_registered() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None))
    assert "synth" in sub.choices
    assert "synthesize" in sub.choices


def test_synthesize_emits_deprecation_warning(capsys) -> None:
    args = build_parser().parse_args(["synthesize", "--check"])
    with patch("llmwiki.cli.resolve_backend") as rb:
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)
    err = capsys.readouterr().err
    assert rc == 0
    assert "deprecated" in err
    assert "llmwiki synth" in err


def test_synth_default_not_deprecated() -> None:
    args = build_parser().parse_args(["synth", "--check"])
    assert args.deprecated_synthesize is False
    assert args.func is cmd_synthesize


def test_synthesize_defaults_deprecated_flag() -> None:
    args = build_parser().parse_args(["synthesize", "--check"])
    assert args.deprecated_synthesize is True


def test_sources_only_and_candidates_only_mutex() -> None:
    parser = build_parser()
    try:
        parser.parse_args(["synth", "--sources-only", "--candidates-only"])
        raised = False
    except SystemExit:
        raised = True
    assert raised
