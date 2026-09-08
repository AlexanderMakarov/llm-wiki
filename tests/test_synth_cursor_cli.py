"""Tests for llmwiki.synth.cursor_cli — Cursor Agent CLI backend (#230)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from llmwiki.synth.base import PER_PAGE_MARKER
from llmwiki.synth.cursor_cli import (
    _BODY_CHAR_CAP,
    _PROBE_PROMPT,
    DEFAULT_CURSOR_MODEL,
    DEFAULT_CURSOR_TIMEOUT,
    CursorCLIError,
    CursorCLISynthesizer,
    lean_argv,
    load_cursor_cli_config,
    resolve_cursor_agent_path,
)

TEMPLATE = "Summarize:\n{body}\nMeta:\n{meta}\n"

_SPLIT_TEMPLATE = (
    "Format rules here.\n"
    "Use suggested-tags and Karpathy-style wikilinks.\n"
    f"{PER_PAGE_MARKER}\n"
    "{{meta}}\n{{body}}\n"
)


def _completed(
    *,
    returncode: int = 0,
    stdout: str = "## Summary\n\nDone.\n",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["agent"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ─── Cursor config defaults / nested ───────────────────────────────────


def test_load_cursor_cli_config_defaults():
    cfg = load_cursor_cli_config({"synthesis": {"backend": "cursor_cli"}})
    assert cfg.model == DEFAULT_CURSOR_MODEL
    assert cfg.model == "composer-2.5"
    assert cfg.timeout == DEFAULT_CURSOR_TIMEOUT
    assert cfg.timeout == 180


def test_load_cursor_cli_config_nested_values():
    cfg = load_cursor_cli_config({
        "synthesis": {
            "cursor_cli": {"model": "composer-2.5-fast", "timeout": 240},
        }
    })
    assert cfg.model == "composer-2.5-fast"
    assert cfg.timeout == 240


# ─── PATH resolution ───────────────────────────────────────────────────


def test_resolve_cursor_agent_path_prefers_agent():
    with patch("llmwiki.synth.cursor_cli.shutil.which") as which:
        which.side_effect = lambda name: {
            "agent": "/usr/bin/agent",
            "cursor-agent": "/usr/bin/cursor-agent",
        }.get(name)
        assert resolve_cursor_agent_path() == "/usr/bin/agent"
        which.assert_any_call("agent")


def test_resolve_cursor_agent_path_falls_back_to_cursor_agent():
    with patch("llmwiki.synth.cursor_cli.shutil.which") as which:
        which.side_effect = lambda name: (
            "/usr/bin/cursor-agent" if name == "cursor-agent" else None
        )
        assert resolve_cursor_agent_path() == "/usr/bin/cursor-agent"


def test_resolve_cursor_agent_path_none_when_missing():
    with patch("llmwiki.synth.cursor_cli.shutil.which", return_value=None):
        assert resolve_cursor_agent_path() is None


# ─── Argv / synthesizer stub ───────────────────────────────────────────


def test_lean_argv_contains_required_flags():
    argv = lean_argv("/bin/agent", model="composer-2.5")
    assert argv[0] == "/bin/agent"
    assert "-p" in argv
    assert argv[argv.index("--mode") + 1] == "ask"
    assert argv[argv.index("--sandbox") + 1] == "enabled"
    assert argv[argv.index("--allowed-tools") + 1] == "truncated_tool_call"
    assert argv[argv.index("--model") + 1] == "composer-2.5"
    assert argv[argv.index("--output-format") + 1] == "text"


def test_synthesizer_argv_matches_lean():
    synth = CursorCLISynthesizer(model="composer-2.5")
    assert synth._argv("/bin/agent") == lean_argv("/bin/agent", model="composer-2.5")


def test_synthesizer_name_and_defaults():
    synth = CursorCLISynthesizer()
    assert synth.name == "cursor-cli"
    assert synth.model == DEFAULT_CURSOR_MODEL
    assert synth.timeout == DEFAULT_CURSOR_TIMEOUT


def test_is_available_false_when_missing():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value=None,
    ):
        assert CursorCLISynthesizer().is_available() is False


def test_is_available_true_after_successful_probe():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(stdout="OK\n"),
    ) as run:
        assert CursorCLISynthesizer().is_available() is True
    assert run.call_args.kwargs["input"] == _PROBE_PROMPT


def test_is_available_false_on_probe_nonzero_exit():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(returncode=1, stdout="", stderr="auth failed"),
    ):
        assert CursorCLISynthesizer().is_available() is False


def test_is_available_false_on_probe_timeout():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="agent", timeout=30),
    ):
        assert CursorCLISynthesizer().is_available() is False


# ─── synthesize_source_page (mocked subprocess) ────────────────────────


def test_synthesize_success_uses_stdin_and_returns_text():
    synth = CursorCLISynthesizer(model="composer-2.5")
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(stdout="## Summary\n\nPage body.\n"),
    ) as run:
        out = synth.synthesize_source_page(
            "session body { braces }", {"slug": "s1"}, TEMPLATE
        )
    assert out == "## Summary\n\nPage body."
    kwargs = run.call_args.kwargs
    assert "session body { braces }" in kwargs["input"]
    assert '"slug": "s1"' in kwargs["input"]
    argv = run.call_args.args[0]
    assert argv[0] == "/bin/agent"
    assert "-p" in argv
    assert argv[argv.index("--mode") + 1] == "ask"
    assert argv[argv.index("--sandbox") + 1] == "enabled"
    assert argv[argv.index("--allowed-tools") + 1] == "truncated_tool_call"
    assert argv[argv.index("--model") + 1] == "composer-2.5"
    assert argv[argv.index("--output-format") + 1] == "text"
    # Prompt is stdin, not a trailing argv token.
    assert kwargs["input"]
    assert TEMPLATE.split("{body}")[0] not in argv


def test_synthesize_timeout_raises():
    synth = CursorCLISynthesizer(timeout=12)
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="agent", timeout=12),
    ):
        with pytest.raises(CursorCLIError, match="timed out after 12s"):
            synth.synthesize_source_page("b", {}, TEMPLATE)


def test_synthesize_sends_stable_half_as_leading_prefix():
    """B1: format rules must reach Agent CLI; leading prefix aids cache."""
    captured: dict[str, str] = {}

    def _capture(*_a, **kwargs):
        captured["input"] = kwargs["input"]
        return _completed(stdout="ok")

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch("llmwiki.synth.cursor_cli.subprocess.run", side_effect=_capture):
        assert CursorCLISynthesizer().synthesize_source_page(
            "body-here", {"slug": "s"}, _SPLIT_TEMPLATE
        ) == "ok"
    text = captured["input"]
    assert "Format rules here." in text
    assert "suggested-tags" in text
    assert "Karpathy-style" in text
    assert PER_PAGE_MARKER in text
    assert "body-here" in text
    # Stable half must lead so automatic prefix caching can match it.
    assert text.index("Format rules here.") < text.index("body-here")


def test_synthesize_missing_binary_raises():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value=None,
    ):
        with pytest.raises(CursorCLIError, match="not found"):
            CursorCLISynthesizer().synthesize_source_page("b", {}, TEMPLATE)


def test_synthesize_nonzero_exit_raises():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(returncode=3, stdout="", stderr="doom"),
    ):
        with pytest.raises(CursorCLIError, match="exited 3.*doom"):
            CursorCLISynthesizer().synthesize_source_page("b", {}, TEMPLATE)


def test_synthesize_empty_completion_raises():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(stdout="  \n"),
    ):
        with pytest.raises(CursorCLIError, match="empty"):
            CursorCLISynthesizer().synthesize_source_page("b", {}, TEMPLATE)


def test_synthesize_truncates_body_to_char_cap():
    body = "x" * (_BODY_CHAR_CAP + 500)
    captured: dict[str, str] = {}

    def _capture(*_a, **kwargs):
        captured["input"] = kwargs["input"]
        return _completed(stdout="ok")

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch("llmwiki.synth.cursor_cli.subprocess.run", side_effect=_capture):
        assert CursorCLISynthesizer().synthesize_source_page(
            body, {}, TEMPLATE
        ) == "ok"
    assert "x" * _BODY_CHAR_CAP in captured["input"]
    assert "x" * (_BODY_CHAR_CAP + 1) not in captured["input"]


def test_synthesize_oserror_raises():
    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=OSError("exec failed"),
    ):
        with pytest.raises(CursorCLIError, match="failed to run"):
            CursorCLISynthesizer().synthesize_source_page("b", {}, TEMPLATE)
