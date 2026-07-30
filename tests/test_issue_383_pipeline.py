"""Tests for #383 — complete CLI build chain (``all --with-synth`` + status hint)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmwiki import cli, pipeline
from llmwiki import cli as cli_mod
from llmwiki.cli import build_parser
from llmwiki.config_schedule import synthesis_status_hint


def test_all_parser_accepts_with_synth_flag():

    args = build_parser().parse_args(["all", "--with-synth", "--synth-force"])
    assert args.with_synth is True
    assert args.synth_force is True


def test_synthesis_status_hint_for_dummy_backend():

    hint = synthesis_status_hint("dummy")
    assert hint is not None
    assert "dummy" in hint
    assert "llmwiki all --with-synth" in hint


def test_synthesis_status_hint_for_ollama_backend():

    hint = synthesis_status_hint("ollama")
    assert hint is not None
    assert "ollama" in hint
    assert "llmwiki synthesize" in hint


def test_cmd_all_with_synth_runs_synthesize_first():

    order: list[str] = []
    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True

    def track(name: str):
        def _stub(*_a, **_k):
            order.append(name)
            if name == "lint":
                return 0, {}
            if name == "synth":
                return {
                    "total_scanned": 0, "new_files": 0,
                    "synthesized": 0, "skipped": 0, "errors": [],
                }
            return 0
        return _stub

    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": False,
        "with_synth": True,
        "synth_force": False,
        "vault": None,
    }
    args = argparse.Namespace(**base)

    with patch.object(pipeline, "resolve_backend", return_value=backend):
        with patch.object(pipeline, "synthesize_new_sessions", side_effect=track("synth")):
            with patch.object(pipeline, "build_site", side_effect=track("build")):
                with patch.object(pipeline, "_run_lint_step", side_effect=track("lint")):
                    rc = cli.cmd_all(args)

    assert rc == 0
    assert order[0] == "synth"
    assert order[1:] == ["build", "lint"]


def test_cmd_all_with_synth_fail_fast_stops_after_synth_failure():

    build_stub = MagicMock(return_value=0)
    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = False
    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": True,
        "with_synth": True,
        "synth_force": False,
        "vault": None,
    }
    args = argparse.Namespace(**base)

    with patch.object(pipeline, "resolve_backend", return_value=backend):
        with patch.object(pipeline, "build_site", build_stub):
            with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
                rc = cli.cmd_all(args)

    assert rc == 1
    assert build_stub.call_count == 0


def test_sync_status_prints_synthesis_hint(capsys, tmp_path, monkeypatch):

    monkeypatch.setattr(
        "llmwiki.config_schedule.load_synthesis_backend",
        lambda *a, **k: "dummy",
    )
    state_file = tmp_path / "llmwiki-state.json"
    state_file.write_text('{"_meta": {"last_sync": "2026-04-01T00:00:00Z"}}', encoding="utf-8")

    rc = cli_mod.cmd_sync_status(
        argparse.Namespace(recent=0, vault=None, state_file=state_file)
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "Hint:" in out
    assert "dummy" in out
