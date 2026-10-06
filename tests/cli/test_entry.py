"""Subprocess smoke tests for top-level ``python -m llmwiki`` entry behaviour."""

from __future__ import annotations

import subprocess
import sys

from llmwiki import __version__


def test_version_flag():
    """``--version`` must print the package version and exit zero."""
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "--version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_version_subcommand():
    """The ``version`` subcommand must print the package version and exit zero."""
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_adapters_lists_claude_code():
    """``adapters`` must list core session-store adapters on stdout."""
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "adapters"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "claude_code" in r.stdout
    assert "codex_cli" in r.stdout
    # obsidian moved to contrib — no longer in default `adapters` output


def test_no_args_prints_help():
    """Invoking ``llmwiki`` with no arguments must print usage and exit zero."""
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "usage:" in r.stdout.lower()
