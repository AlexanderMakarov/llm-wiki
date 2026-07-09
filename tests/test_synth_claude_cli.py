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
