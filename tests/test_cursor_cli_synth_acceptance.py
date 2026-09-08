"""Whole-feature acceptance tests for #230: Cursor Agent CLI synthesis backend.

# @layer: integration
# @spec: 226-cursor-cli-synth-backend
# @regression

Shared resolve/CLI/overview contracts live in ``test_synth_backends_shared.py``.
This module keeps Cursor-specific acceptance: lean argv, page write, probe
failure without failover, and packaged pricing aliases.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.cache import MODEL_PRICING, resolve_pricing_model
from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth.cursor_cli import (
    DEFAULT_CURSOR_MODEL,
    DEFAULT_CURSOR_TIMEOUT,
    lean_argv,
    load_cursor_cli_config,
)

_DOC = """---
title: "Acceptance fixture"
slug: cursor-accept
project: demo
---

# Fixture

Body for cursor_cli acceptance synth.
"""

_CURSOR_PAGE = "## Summary\n\nCursor-synthesized acceptance page.\n"


def _completed(
    *,
    returncode: int = 0,
    stdout: str = _CURSOR_PAGE,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["agent"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    (vault / "raw" / "docs" / "cursor-accept.md").write_text(_DOC, encoding="utf-8")
    return vault


def _mock_agent_run(*, probe_ok: bool = True, page: str = _CURSOR_PAGE):
    """Return a subprocess.run side_effect: probe then synth pages."""

    def _side_effect(*_args, **kwargs):
        prompt = kwargs.get("input") or ""
        if "Reply with exactly: OK" in prompt:
            if not probe_ok:
                return _completed(returncode=1, stdout="", stderr="auth failed")
            return _completed(stdout="OK\n")
        return _completed(stdout=page)

    return _side_effect


def test_nested_config_defaults_to_cheapest_composer() -> None:  # @regression
    """R3: default Cursor model is ``composer-2.5``."""
    cfg = load_cursor_cli_config({"synthesis": {"backend": "cursor_cli"}})
    assert cfg.model == DEFAULT_CURSOR_MODEL == "composer-2.5"
    assert cfg.timeout == DEFAULT_CURSOR_TIMEOUT


def test_lean_argv_is_non_interactive_and_has_no_worktree_flags() -> None:  # @regression
    """R3/R4: lean invocation uses ask + sandbox + tiny allowlist; no force/yolo/worktree."""
    argv = lean_argv("/bin/agent", model="composer-2.5")
    assert argv[0] == "/bin/agent"
    assert "-p" in argv
    assert argv[argv.index("--mode") + 1] == "ask"
    assert argv[argv.index("--sandbox") + 1] == "enabled"
    assert argv[argv.index("--allowed-tools") + 1] == "truncated_tool_call"
    assert argv[argv.index("--model") + 1] == "composer-2.5"
    forbidden = ("--force", "--yolo", "--approve-mcps", "--worktree")
    for flag in forbidden:
        assert flag not in argv


def test_cli_synth_cursor_cli_writes_real_source_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:  # @regression
    """R1/R4: ``--backend cursor_cli`` synthesizes a real page via mocked Agent CLI."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy", "cursor_cli": {"model": "composer-2.5"}}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=_mock_agent_run(),
    ):
        args = build_parser().parse_args([
            "synth",
            "--backend", "cursor_cli",
            "--sources-only",
            "--vault", str(vault),
        ])
        rc = cmd_synthesize(args)

    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    page = vault / "wiki" / "sources" / "demo" / "cursor-accept.md"
    assert page.is_file()
    body = page.read_text(encoding="utf-8")
    assert "Cursor-synthesized acceptance page" in body
    assert "placeholder" not in body.lower()


def test_cli_unavailable_cursor_cli_fails_without_failover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R5: unavailable Cursor fails hard — no silent dummy fallback."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "cursor_cli"}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=_mock_agent_run(probe_ok=False),
    ):
        args = build_parser().parse_args([
            "synth", "--backend", "cursor_cli", "--sources-only", "--vault", str(vault),
        ])
        rc = cmd_synthesize(args)

    assert rc == 1
    assert not (vault / "wiki" / "sources" / "demo" / "cursor-accept.md").exists()
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "not available" in combined.lower() or "Available: False" in combined


def test_check_requires_successful_probe_not_binary_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R5: PATH alone is not enough — probe failure makes ``--check`` fail."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "cursor_cli"}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(returncode=1, stderr="not logged in"),
    ):
        args = build_parser().parse_args(["synth", "--check", "--vault", str(vault)])
        rc = cmd_synthesize(args)

    out = capsys.readouterr().out
    assert rc == 1
    assert "Available: False" in out


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("composer", "composer-2.5"),
        ("composer-2.5-fast", "composer-2.5-fast"),
        ("cursor-grok-4.6-high", "grok-4.6"),
        ("grok-4.5-fast", "grok-4.5-fast"),
    ],
)
def test_cursor_pricing_aliases_on_packaged_rate_card(alias: str, canonical: str) -> None:  # @regression
    """R7: Cursor model ids and aliases resolve on ``model_pricing.csv``."""
    resolved = resolve_pricing_model(alias)
    assert resolved == canonical
    assert canonical in MODEL_PRICING
    rates = MODEL_PRICING[canonical]
    assert rates["input"] > 0
    assert rates["output"] > 0
