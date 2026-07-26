"""Tests for llmwiki.synth.claude_cli — synchronous `claude -p` backend (#16)."""

from __future__ import annotations

import pytest

from llmwiki.synth.claude_cli import ClaudeCLIError, ClaudeCLISynthesizer
from llmwiki.synth.pipeline import resolve_backend

TEMPLATE = "Summarize:\n{body}\nMeta:\n{meta}\n"


def _script(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    p.chmod(0o755)
    return p


def test_resolve_backend_claude():
    backend = resolve_backend({"synthesis": {"backend": "claude",
                                             "claude_path": "/nonexistent/claude",
                                             "claude_model": "some-model",
                                             "timeout": 42}})
    assert isinstance(backend, ClaudeCLISynthesizer)
    assert backend.name == "claude-cli"
    assert backend.model == "some-model"
    assert backend.timeout == 42


def test_unavailable_when_cli_missing(tmp_path):
    backend = ClaudeCLISynthesizer(claude_path=str(tmp_path / "nope"))
    assert not backend.is_available()


def test_synthesize_renders_prompt_and_returns_completion(tmp_path):
    # Echo the prompt back so we can assert rendering; prefix marks output.
    script = _script(tmp_path, "claude-echo", "#!/bin/sh\nprintf 'PAGE: '\ncat\n")
    backend = ClaudeCLISynthesizer(claude_path=str(script))
    assert backend.is_available()
    out = backend.synthesize_source_page(
        "session body { with braces }", {"slug": "s1"}, TEMPLATE
    )
    assert out.startswith("PAGE: Summarize:")
    assert "session body { with braces }" in out   # {body} replaced, braces intact
    assert '"slug": "s1"' in out                   # {meta} replaced with JSON


def test_nonzero_exit_raises(tmp_path):
    script = _script(tmp_path, "claude-fail", "#!/bin/sh\ncat > /dev/null\necho doom >&2\nexit 3\n")
    backend = ClaudeCLISynthesizer(claude_path=str(script))
    with pytest.raises(ClaudeCLIError, match="exited 3.*doom"):
        backend.synthesize_source_page("b", {}, TEMPLATE)


def test_empty_completion_raises(tmp_path):
    script = _script(tmp_path, "claude-empty", "#!/bin/sh\ncat > /dev/null\n")
    backend = ClaudeCLISynthesizer(claude_path=str(script))
    with pytest.raises(ClaudeCLIError, match="empty"):
        backend.synthesize_source_page("b", {}, TEMPLATE)


def test_model_flag_forwarded(tmp_path):
    script = _script(tmp_path, "claude-args", '#!/bin/sh\ncat > /dev/null\necho "argv:$@"\n')
    backend = ClaudeCLISynthesizer(claude_path=str(script), model="claude-haiku-4-5")
    out = backend.synthesize_source_page("b", {}, TEMPLATE)
    assert "--model claude-haiku-4-5" in out


def test_missing_cli_raises_with_hint(tmp_path):
    backend = ClaudeCLISynthesizer(claude_path=str(tmp_path / "nope"))
    with pytest.raises(ClaudeCLIError, match="ollama"):
        backend.synthesize_source_page("b", {}, TEMPLATE)


# ─── lean mode: strip agent scaffolding from every call ────────────────

# One argv entry per line so empty-string args (`--tools ""`) stay visible.
_ARGV_DUMP = '#!/bin/sh\ncat > /dev/null\nfor a in "$@"; do echo "[$a]"; done\n'


def _argv_of(tmp_path, name, **kwargs):
    script = _script(tmp_path, name, _ARGV_DUMP)
    backend = ClaudeCLISynthesizer(claude_path=str(script), **kwargs)
    out = backend.synthesize_source_page("b", {}, TEMPLATE)
    return [line[1:-1] for line in out.splitlines()]


def test_lean_flags_present_by_default(tmp_path):
    argv = _argv_of(tmp_path, "claude-lean")
    # Each flag drops one source of per-call scaffolding overhead.
    assert "--strict-mcp-config" in argv
    assert "--disable-slash-commands" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1].startswith("You synthesize")


def test_lean_tools_flag_is_followed_by_a_flag(tmp_path):
    """`--tools` is variadic: a bare "" must not swallow the next argument."""
    argv = _argv_of(tmp_path, "claude-variadic")
    assert argv[argv.index("--tools") + 2].startswith("--")


def test_lean_can_be_disabled(tmp_path):
    argv = _argv_of(tmp_path, "claude-fat", lean=False)
    assert argv == ["-p", "-"]


def test_lean_composes_with_model_flag(tmp_path):
    argv = _argv_of(tmp_path, "claude-lean-model", model="sonnet")
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert "--strict-mcp-config" in argv


def test_resolve_backend_lean_defaults_on_and_opts_out():
    base = {"backend": "claude", "claude_path": "/nonexistent/claude"}
    assert resolve_backend({"synthesis": base}).lean is True
    # Only an explicit `false` opts out — a typo'd value keeps the default.
    assert resolve_backend({"synthesis": {**base, "claude_lean": False}}).lean is False
    assert resolve_backend({"synthesis": {**base, "claude_lean": "nope"}}).lean is True
