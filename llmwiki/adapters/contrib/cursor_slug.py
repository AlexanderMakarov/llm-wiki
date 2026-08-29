"""Shared Cursor project-slug helper (IDE + Agent CLI) for #126 prep."""

from __future__ import annotations

from llmwiki.adapters.base import _safe_project_slug


def cursor_workspace_slug(workspace_hash: str) -> str:
    """``cursor-<first-12-chars>`` — shared by ``cursor`` and ``cursor_cli``."""
    h = (workspace_hash or "").strip()
    return _safe_project_slug(f"cursor-{h[:12]}") if h else "cursor-unnamed"
