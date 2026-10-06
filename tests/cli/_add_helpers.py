"""Shared helpers for ``llmwiki add`` CLI tests."""

from __future__ import annotations

from pathlib import Path

import llmwiki.cli as cli_mod


def scratch_vault(tmp_path: Path) -> Path:
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


def fake_claude(tmp_path: Path, body: str = "## Summary\\nSynthesized synchronously."):
    """Executable stub standing in for the ``claude`` CLI."""
    script = tmp_path / "claude-stub"
    script.write_text(f'#!/bin/sh\ncat > /dev/null\nprintf "{body}\\n"\n')
    script.chmod(0o755)
    return script


def add_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True, exist_ok=True)
    (vault / "wiki").mkdir()
    return vault


def run_add(vault: Path, *argv: str) -> int:
    args = cli_mod.build_parser().parse_args(["add", "--vault", str(vault), *argv])
    return args.func(args)
