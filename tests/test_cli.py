"""Smoke tests for the CLI entry point."""

from __future__ import annotations

import subprocess
import sys

from llmwiki import __version__


def test_version_flag():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "--version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_version_subcommand():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_adapters_lists_claude_code():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "adapters"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "claude_code" in r.stdout
    assert "codex_cli" in r.stdout
    # obsidian moved to contrib — no longer in default `adapters` output


def test_no_args_prints_help():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki"],
        capture_output=True, text=True,
    )
    # Should print help and exit 0
    assert r.returncode == 0
    assert "usage" in r.stdout.lower() or "llmwiki" in r.stdout


def _scratch_vault(tmp_path):
    """Minimal existing directory to pass as --vault.

    These tests run `llmwiki add` in a subprocess, so monkeypatching
    can't stop `_apply_default_vault` from reading this machine's
    (gitignored) dev config.json — which may set `vault.default_path`
    to something that doesn't resolve here (or resolves to a real vault
    we don't want to touch). Passing an explicit --vault short-circuits
    that lookup (`_apply_default_vault` only fills `args.vault` when it
    is still None) and keeps the test hermetic on any machine.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def test_add_dry_run_local_md(tmp_path):
    src = tmp_path / "sample.md"
    src.write_text("# Sample Doc\n\nsome content\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--dry-run",
         "--vault", str(_scratch_vault(tmp_path)), str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Sample Doc" in r.stdout
    assert "dry-run" in r.stdout


def test_add_requires_source():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


def test_add_title_with_multiple_sources_rejected(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("# A\n")
    b.write_text("# B\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--title", "T", "--dry-run",
         "--vault", str(_scratch_vault(tmp_path)), str(a), str(b)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "--title" in r.stderr


def test_llm_wiki_add_entry_point(tmp_path):
    src = tmp_path / "sample.md"
    src.write_text("# Entry Point Doc\n\ncontent\n")
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; from llmwiki.cli import main_add; sys.exit(main_add())",
         "--dry-run", "--vault", str(_scratch_vault(tmp_path)), str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Entry Point Doc" in r.stdout


def test_add_agent_delegate_unavailable_defers_not_fails(tmp_path, monkeypatch, capsys):
    """PR #19 field report: an unavailable agent-delegate backend is the
    EXPECTED state outside an agent runtime — cmd_add must print a
    friendly deferral note and exit 0, not an error."""
    import llmwiki.cli as cli_mod
    import llmwiki.synth.pipeline as pipeline_mod
    from llmwiki.synth.agent_delegate import AgentDelegateSynthesizer

    for var in ("LLMWIKI_AGENT_MODE", "CLAUDE_CODE", "CLAUDECODE", "CODEX_CLI", "CURSOR_AGENT"):
        monkeypatch.delenv(var, raising=False)

    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()
    src = tmp_path / "doc.md"
    src.write_text("# Deferred Doc\n\nbody\n")

    monkeypatch.setattr(pipeline_mod, "resolve_backend",
                        lambda cfg: AgentDelegateSynthesizer())
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    args = cli_mod.build_parser().parse_args(["add", "--vault", str(vault), str(src)])
    rc = args.func(args)
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "synthesis deferred" in out.out
    assert "not available" not in out.err
    assert (vault / "raw" / "docs" / "deferred-doc" / "deferred-doc.md").exists()


def test_add_other_unavailable_backend_still_fails(tmp_path, monkeypatch, capsys):
    """A genuinely-down backend (e.g. ollama) keeps the error path."""
    import llmwiki.cli as cli_mod
    import llmwiki.synth.pipeline as pipeline_mod
    from llmwiki.synth.base import BaseSynthesizer

    class _DownBackend(BaseSynthesizer):
        name = "ollama"

        def is_available(self):
            return False

        def synthesize_source_page(self, raw_body, meta, prompt_template):  # pragma: no cover
            return ""

    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()
    src = tmp_path / "doc.md"
    src.write_text("# Down Backend Doc\n\nbody\n")

    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda cfg: _DownBackend())
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    args = cli_mod.build_parser().parse_args(["add", "--vault", str(vault), str(src)])
    rc = args.func(args)
    out = capsys.readouterr()
    assert rc == 2
    assert "not available" in (out.out + out.err)


def test_pyproject_add_extra_includes_markitdown_backends():
    """markitdown gates each converter behind its own extra; a bare
    `markitdown` can't read the PDFs/DOCX this feature advertises
    (PR #19 field report)."""
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert "markitdown[pdf,docx,pptx,xlsx]" in text
