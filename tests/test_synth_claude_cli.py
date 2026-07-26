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

# Delimiter-separated (not newline) so empty-string args (`--tools ""`) stay
# visible AND multi-line args like the system prompt survive intact. It has
# to be printable: the backend calls .strip() on stdout, and Python counts
# the ASCII separator controls (\x1c-\x1f) as whitespace.
_ARGV_SEP = "|@ARG@|"
_ARGV_DUMP = (
    '#!/bin/sh\ncat > /dev/null\n'
    'for a in "$@"; do printf \'%s|@ARG@|\' "$a"; done\n'
)


def _argv_of(tmp_path, name, template=TEMPLATE, **kwargs):
    script = _script(tmp_path, name, _ARGV_DUMP)
    backend = ClaudeCLISynthesizer(claude_path=str(script), **kwargs)
    out = backend.synthesize_source_page("b", {}, template)
    return out.split(_ARGV_SEP)[:-1]


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


# ─── cached prefix: stable half of the template → provider cache ───────

_SPLIT_TEMPLATE = (
    "Format rules here.\n\nVocabulary: <topic name=\"X\" />\n\n"
    "## Session to synthesize\n\nFrontmatter:\n{meta}\n\nBody:\n{body}\n"
)


def test_split_prompt_template_separates_stable_from_per_page():
    from llmwiki.synth.base import split_prompt_template
    stable, per_page = split_prompt_template(_SPLIT_TEMPLATE)
    assert "Format rules here." in stable
    assert "<topic" in stable
    # The stable half must carry no per-page placeholders, or it would
    # differ every page and never be cached.
    assert "{body}" not in stable and "{meta}" not in stable
    assert per_page.startswith("## Session to synthesize")
    assert "{body}" in per_page and "{meta}" in per_page


def test_split_prompt_template_tolerates_a_custom_template():
    """No marker → everything stays in the user prompt, nothing is lost."""
    from llmwiki.synth.base import split_prompt_template
    stable, per_page = split_prompt_template("Just do it: {body}")
    assert stable == ""
    assert per_page == "Just do it: {body}"


def test_claude_sends_stable_half_as_system_prompt(tmp_path):
    argv = _argv_of(tmp_path, "claude-split", template=_SPLIT_TEMPLATE)
    system = argv[argv.index("--system-prompt") + 1]
    assert "Format rules here." in system
    assert "<topic" in system
    assert "{body}" not in system


def test_claude_body_goes_to_stdin_not_the_system_prompt(tmp_path):
    """The per-page half must stay out of the cached slot."""
    script = _script(tmp_path, "claude-stdin", "#!/bin/sh\ncat\n")
    backend = ClaudeCLISynthesizer(claude_path=str(script))
    out = backend.synthesize_source_page(
        "UNIQUE-BODY-MARKER", {"slug": "s"}, _SPLIT_TEMPLATE
    )
    assert "UNIQUE-BODY-MARKER" in out          # reached the model via stdin
    assert "Format rules here." not in out      # stable half went to --system-prompt


def test_custom_template_still_gets_a_system_prompt(tmp_path):
    """With nothing stable to cache, fall back to the short default."""
    argv = _argv_of(tmp_path, "claude-nosplit", template="Summarize: {body}")
    assert argv[argv.index("--system-prompt") + 1].startswith("You synthesize")


def test_overview_model_is_configurable_not_hardcoded():
    from llmwiki.synth.claude_cli import (
        DEFAULT_OVERVIEW_MODEL,
        overview_argv,
        resolve_overview_model,
    )
    assert resolve_overview_model({}) == DEFAULT_OVERVIEW_MODEL
    assert resolve_overview_model(
        {"synthesis": {"overview_model": "sonnet"}}
    ) == "sonnet"
    # Blank config value must not win over the default.
    assert resolve_overview_model(
        {"synthesis": {"overview_model": "  "}}
    ) == DEFAULT_OVERVIEW_MODEL
    # The overview call gets the same scaffolding-stripping flags.
    argv = overview_argv("/bin/claude", "sonnet")
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--tools") + 1] == ""


def test_resolve_backend_lean_defaults_on_and_opts_out():
    base = {"backend": "claude", "claude_path": "/nonexistent/claude"}
    assert resolve_backend({"synthesis": base}).lean is True
    # Only an explicit `false` opts out — a typo'd value keeps the default.
    assert resolve_backend({"synthesis": {**base, "claude_lean": False}}).lean is False
    assert resolve_backend({"synthesis": {**base, "claude_lean": "nope"}}).lean is True
