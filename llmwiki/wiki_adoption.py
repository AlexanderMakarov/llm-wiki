"""Best-effort detection of sessions that used the llmwiki MCP (#52).

MCP ``usage/*.jsonl`` is the agent-agnostic usage signal. Session transcripts
are a second series: Claude Code often records ``mcp__llmwiki__wiki_query`` in
``tools_used``, while Cursor commonly only lists ``CallMcpTool`` and buries the
server name in the body. This module accepts both.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# Explicit llmwiki MCP tool names (Claude Code + some Cursor exports).
_LLMWIKI_TOOL_RE = re.compile(
    r"(?:mcp__llmwiki__|mcp_llmwiki_)[A-Za-z0-9_]+",
    re.IGNORECASE,
)
# Cursor opacity: CallMcpTool args often name the server in the transcript.
_LLMWIKI_BODY_RE = re.compile(
    r"(?:mcp__llmwiki__|mcp_llmwiki_|"
    r"['\"]server['\"]\s*:\s*['\"]llmwiki['\"]|"
    r"\bserver\s*[:=]\s*llmwiki\b)",
    re.IGNORECASE,
)
_CURSOR_MCP_WRAPPERS = frozenset({"CallMcpTool", "GetMcpTools"})


def _tools_list(meta: Mapping[str, Any]) -> list[str]:
    raw = meta.get("tools_used")
    if isinstance(raw, list):
        return [str(t) for t in raw if t]
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        return [t.strip().strip("'\"") for t in text.split(",") if t.strip()]
    return []


def looks_like_llmwiki_tool(name: str) -> bool:
    return bool(name) and bool(_LLMWIKI_TOOL_RE.search(name.strip()))


def session_used_wiki(
    meta: Mapping[str, Any],
    body: str | None = None,
) -> bool:
    """True when this session best-effort touched the llmwiki MCP."""
    tools = _tools_list(meta)
    if any(looks_like_llmwiki_tool(t) for t in tools):
        return True
    if body and any(t in _CURSOR_MCP_WRAPPERS for t in tools):
        # Cap the scan — full transcripts can be huge; markers appear early
        # in tool-call dumps when present.
        return bool(_LLMWIKI_BODY_RE.search(body[:200_000]))
    if body and _LLMWIKI_TOOL_RE.search(body[:200_000]):
        # Some adapters omit tools_used but still dump tool names in the body.
        return True
    return False


def session_date(meta: Mapping[str, Any]) -> str | None:
    """Return ``YYYY-MM-DD`` from frontmatter, or None."""
    for key in ("date", "started", "ended"):
        val = meta.get(key)
        if isinstance(val, str) and len(val) >= 10 and val[4] == "-" and val[7] == "-":
            return val[:10]
    return None


def daily_wiki_sessions(
    sessions: Iterable[tuple[Mapping[str, Any], str]],
) -> dict[str, int]:
    """Count wiki-using sessions per ``YYYY-MM-DD``.

    Each item is ``(meta, body)``. Body may be empty when only frontmatter is
    available (Cursor detection then relies on explicit tool names).
    """
    counts: dict[str, int] = {}
    for meta, body in sessions:
        if not session_used_wiki(meta, body):
            continue
        day = session_date(meta)
        if not day:
            continue
        counts[day] = counts.get(day, 0) + 1
    return dict(sorted(counts.items()))


def daily_wiki_sessions_from_dir(sessions_dir: Path) -> dict[str, int]:
    """Scan ``raw/sessions/**/*.md`` and return wiki-using counts by date."""
    if not sessions_dir.is_dir():
        return {}
    items: list[tuple[dict[str, Any], str]] = []
    for p in sessions_dir.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = _parse_frontmatter_lite(text)
        # Body after frontmatter — enough for Cursor CallMcpTool markers.
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]
        items.append((meta, body))
    return daily_wiki_sessions(items)


def _parse_frontmatter_lite(text: str) -> dict[str, Any]:
    """Minimal frontmatter parse — date + tools_used only."""
    meta: dict[str, Any] = {}
    if not text.startswith("---"):
        return meta
    parts = text.split("---", 2)
    if len(parts) < 3:
        return meta
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key in {"date", "started", "ended"}:
            meta[key] = val.strip("'\"")
        elif key == "tools_used":
            meta[key] = val
    return meta
