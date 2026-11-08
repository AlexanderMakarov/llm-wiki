"""Patch ClaudeCodeAdapter + Path.home() for convert/sync tests under a synthetic home."""

from __future__ import annotations

from builtins import classmethod
from pathlib import Path

import pytest

import llmwiki.convert as convert_mod
from llmwiki.adapters.claude_code import ClaudeCodeAdapter


def patch_claude_session_store(
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
    *,
    repo_root_parent: Path | None = None,
) -> Path:
    """Point the Claude adapter at ``home/.claude/projects`` and align ``Path.home()``."""
    store = home / ".claude" / "projects"
    monkeypatch.setattr(
        ClaudeCodeAdapter,
        "default_session_store_path",
        classmethod(lambda cls, _store=store: _store),
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls, _home=home: _home))
    if repo_root_parent is not None:
        monkeypatch.setattr(convert_mod, "REPO_ROOT", repo_root_parent / "repo")
    return store
