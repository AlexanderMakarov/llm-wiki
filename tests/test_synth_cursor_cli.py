"""Tests for llmwiki.synth.cursor_cli — Cursor Agent CLI backend (#230)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from llmwiki.synth.base import PER_PAGE_MARKER, DummySynthesizer
from llmwiki.synth.claude_cli import (
    DEFAULT_CLAUDE_TIMEOUT,
    ClaudeConfig,
    load_claude_config,
)
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
from llmwiki.synth.pipeline import resolve_backend

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

# ─── Nested Claude config (shared nested-wins pattern) ─────────────────


def test_load_claude_config_prefers_nested_block():
    cfg = load_claude_config({
        "synthesis": {
            "claude": {
                "model": "opus",
                "timeout": 99,
                "lean": False,
                "effort": "low",
                "path": "/nested/claude",
            },
            "claude_model": "sonnet",
            "claude_timeout": 180,
            "claude_lean": True,
            "claude_effort": "high",
            "claude_path": "/flat/claude",
        }
    })
    assert isinstance(cfg, ClaudeConfig)
    assert cfg.model == "opus"
    assert cfg.timeout == 99
    assert cfg.lean is False
    assert cfg.effort == "low"
    assert cfg.path == "/nested/claude"


def test_load_claude_config_flat_fallback():
    cfg = load_claude_config({
        "synthesis": {
            "claude_model": "haiku",
            "claude_timeout": 120,
            "claude_lean": False,
            "claude_effort": "low",
            "claude_path": "/flat/claude",
        }
    })
    assert cfg.model == "haiku"
    assert cfg.timeout == 120
    assert cfg.lean is False
    assert cfg.effort == "low"
    assert cfg.path == "/flat/claude"


def test_load_claude_config_ignores_shared_ollama_timeout():
    cfg = load_claude_config({
        "synthesis": {"backend": "claude", "timeout": 60}
    })
    assert cfg.timeout == DEFAULT_CLAUDE_TIMEOUT


def test_resolve_backend_claude_reads_nested_block():
    backend = resolve_backend({
        "synthesis": {
            "backend": "claude",
            "claude": {"model": "nested-model", "timeout": 77, "path": "/n/claude"},
            "claude_model": "flat-model",
        }
    })
    assert backend.model == "nested-model"
    assert backend.timeout == 77
    assert backend.claude_path == "/n/claude"


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


def test_load_cursor_cli_config_ignores_shared_timeout():
    """Flat Ollama ``timeout`` must not cap the Cursor per-page budget."""
    cfg = load_cursor_cli_config({
        "synthesis": {"backend": "cursor_cli", "timeout": 60}
    })
    assert cfg.timeout == DEFAULT_CURSOR_TIMEOUT


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


# ─── resolve_backend wiring ────────────────────────────────────────────


def test_resolve_backend_cursor_cli():
    backend = resolve_backend({
        "synthesis": {
            "backend": "cursor_cli",
            "cursor_cli": {"model": "composer-2.5-fast", "timeout": 90},
        }
    })
    assert isinstance(backend, CursorCLISynthesizer)
    assert backend.name == "cursor-cli"
    assert backend.model == "composer-2.5-fast"
    assert backend.timeout == 90


def test_resolve_backend_cursor_cli_defaults():
    backend = resolve_backend({"synthesis": {"backend": "cursor_cli"}})
    assert isinstance(backend, CursorCLISynthesizer)
    assert backend.model == "composer-2.5"
    assert backend.timeout == 180


def test_resolve_backend_unknown_still_warns_to_dummy(caplog):
    with caplog.at_level("WARNING"):
        backend = resolve_backend({"synthesis": {"backend": "not-a-backend"}})
    assert isinstance(backend, DummySynthesizer)
    assert any("Unknown synthesis.backend" in r.message for r in caplog.records)
