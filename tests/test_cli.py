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


def test_add_dry_run_local_md(tmp_path):
    src = tmp_path / "sample.md"
    src.write_text("# Sample Doc\n\nsome content\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--dry-run", str(src)],
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
         str(a), str(b)],
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
         "--dry-run", str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Entry Point Doc" in r.stdout
