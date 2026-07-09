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


def _fake_claude(tmp_path, body="## Summary\\nSynthesized synchronously."):
    """Executable stub standing in for the `claude` CLI: swallows the
    stdin prompt, prints a canned page."""
    script = tmp_path / "claude-stub"
    script.write_text(f'#!/bin/sh\ncat > /dev/null\nprintf "{body}\\n"\n')
    script.chmod(0o755)
    return script


def _add_vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()
    return vault


def _run_add(cli_mod, vault, *argv):
    args = cli_mod.build_parser().parse_args(["add", "--vault", str(vault), *argv])
    return args.func(args)


def test_add_configured_claude_backend_synthesizes_synchronously(tmp_path, monkeypatch, capsys):
    """`add` uses THE backend configured once for the whole repository
    (config.json synthesis.backend) and produces a real page in the same
    invocation — from a plain terminal or inside an agent session."""
    import llmwiki.cli as cli_mod
    import llmwiki.config_schedule as config_mod

    vault = _add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Sync Doc\n\nbody\n")

    claude = _fake_claude(tmp_path)
    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "claude", "claude_path": str(claude)},
    })
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    rc = _run_add(cli_mod, vault, str(src))
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "claude-cli" in out.out
    pages = list((vault / "wiki" / "sources").rglob("*.md"))
    assert pages, "expected a synthesized wiki/sources page in the same run"
    assert "Synthesized synchronously" in pages[0].read_text()
    assert (vault / "raw" / "docs" / "sync-doc" / "sync-doc.md").exists()


def test_add_synthesizes_only_written_docs(tmp_path, monkeypatch, capsys):
    """`add` must not drain the unsynthesized backlog — only the docs it wrote."""
    import llmwiki.cli as cli_mod
    import llmwiki.config_schedule as config_mod
    import llmwiki.synth.pipeline as pipeline_mod

    vault = _add_vault(tmp_path)
    # Pre-existing unsynthesized doc that must NOT be touched by this add.
    backlog = vault / "raw" / "docs" / "old-backlog" / "old-backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text("---\ntitle: Old\nproject: docs\nslug: old-backlog\n---\n\n# Old\n", encoding="utf-8")

    src = tmp_path / "new.md"
    src.write_text("# Brand New\n\nbody\n")

    captured: dict = {}

    def _fake_synth(**kwargs):
        captured.update(kwargs)
        return {
            "total_scanned": 1,
            "new_files": 1,
            "synthesized": 1,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        }

    class _Ok:
        name = "dummy"
        def is_available(self):
            return True

    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipeline_mod, "synthesize_new_sessions", _fake_synth)
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)
    # expected_source_page check: create the page so rollback doesn't fire
    def _expected(raw_path, sources_dir):
        from pathlib import Path
        p = Path(sources_dir) / "docs" / "brand-new.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Brand New\n", encoding="utf-8")
        return p
    import llmwiki.add_doc as add_doc_mod
    monkeypatch.setattr(add_doc_mod, "expected_source_page", _expected)

    rc = _run_add(cli_mod, vault, str(src))
    assert rc == 0
    assert "only_paths" in captured
    only = {str(p) for p in captured["only_paths"]}
    assert any("brand-new" in p for p in only)
    assert not any("old-backlog" in p for p in only)

def test_add_readd_unchanged_skips_without_synth(tmp_path, monkeypatch, capsys):
    """Re-adding identical content exits 0 and does not synthesize/build (#22)."""
    import llmwiki.cli as cli_mod

    vault = _add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Repeat Doc\n\nsame body\n")

    synth_called = {"n": 0}
    build_called = {"n": 0}

    import llmwiki.synth.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "synthesize_new_sessions",
                        lambda **kw: (synth_called.__setitem__("n", synth_called["n"] + 1) or {}))
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site",
                        lambda **kw: (build_called.__setitem__("n", build_called["n"] + 1) or 0))

    rc1 = _run_add(cli_mod, vault, "--no-synthesize", "--no-build", str(src))
    assert rc1 == 0
    assert synth_called["n"] == 0
    assert build_called["n"] == 0

    rc2 = _run_add(cli_mod, vault, str(src))
    out = capsys.readouterr()
    assert rc2 == 0, out.err
    assert synth_called["n"] == 0, "re-add must not trigger synthesis"
    assert build_called["n"] == 0, "re-add must not trigger build"
    assert "already present as repeat-doc" in out.out
    assert len(list((vault / "raw" / "docs").rglob("*.md"))) == 1


def test_add_unavailable_backend_rolls_back_raw_docs(tmp_path, monkeypatch, capsys):
    """No half-added docs: when the configured backend can't synthesize,
    the just-added raw docs are removed and add fails — only
    --no-synthesize skips synthesis."""
    import llmwiki.cli as cli_mod
    import llmwiki.config_schedule as config_mod

    vault = _add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Orphan Doc\n\nbody\n")

    class _Unavailable:
        name = "offline"
        def is_available(self):
            return False

    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    import llmwiki.synth.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Unavailable())
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    rc = _run_add(cli_mod, vault, str(src))
    out = capsys.readouterr()
    assert rc == 2
    assert "--no-synthesize" in out.err
    assert "olled back" in out.err
    assert not (vault / "raw" / "docs" / "orphan-doc").exists()
    log = vault / "wiki" / "log.md"
    assert not log.exists() or "Orphan Doc" not in log.read_text()


def test_add_failed_synthesis_rolls_back_raw_docs(tmp_path, monkeypatch, capsys):
    """A backend that errors per page (claude CLI exiting 1) leaves no
    wiki page — the raw doc must be rolled back, not left half-added."""
    import llmwiki.cli as cli_mod
    import llmwiki.config_schedule as config_mod

    vault = _add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Broken Doc\n\nbody\n")

    broken = tmp_path / "claude-broken"
    broken.write_text("#!/bin/sh\ncat > /dev/null\necho boom >&2\nexit 1\n")
    broken.chmod(0o755)
    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "claude", "claude_path": str(broken)},
    })
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    rc = _run_add(cli_mod, vault, str(src))
    out = capsys.readouterr()
    assert rc == 2
    assert "olled back" in out.err
    assert not (vault / "raw" / "docs" / "broken-doc").exists()


def test_add_no_synthesize_keeps_docs(tmp_path, monkeypatch, capsys):
    """--no-synthesize is the explicit opt-out: docs stay raw-only."""
    import llmwiki.cli as cli_mod

    vault = _add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Raw Only Doc\n\nbody\n")
    import llmwiki.build as build_mod
    monkeypatch.setattr(build_mod, "build_site", lambda **kw: 0)

    rc = _run_add(cli_mod, vault, "--no-synthesize", str(src))
    assert rc == 0
    assert (vault / "raw" / "docs" / "raw-only-doc" / "raw-only-doc.md").exists()


def test_pyproject_add_extra_includes_markitdown_backends():
    """markitdown gates each converter behind its own extra; a bare
    `markitdown` can't read the PDFs/DOCX this feature advertises
    (PR #19 field report)."""
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert "markitdown[pdf,docx,pptx,xlsx]" in text
