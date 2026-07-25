"""Tests for best-effort wiki MCP session adoption (#52)."""
from __future__ import annotations

from pathlib import Path

from llmwiki.wiki_adoption import (
    daily_wiki_sessions,
    daily_wiki_sessions_from_dir,
    looks_like_llmwiki_tool,
    session_used_wiki,
)


def test_looks_like_llmwiki_tool_variants():
    assert looks_like_llmwiki_tool("mcp__llmwiki__wiki_query")
    assert looks_like_llmwiki_tool("mcp_llmwiki_wiki_search")
    assert not looks_like_llmwiki_tool("mcp__github__issue_read")
    assert not looks_like_llmwiki_tool("CallMcpTool")
    assert not looks_like_llmwiki_tool("Read")


def test_session_used_wiki_from_tools_used():
    meta = {"tools_used": ["Bash", "mcp__llmwiki__wiki_query", "Read"],
            "date": "2026-07-12"}
    assert session_used_wiki(meta, body="") is True


def test_session_used_wiki_cursor_callmcp_with_body_marker():
    meta = {"tools_used": ["GetMcpTools", "CallMcpTool", "Read"],
            "date": "2026-07-24"}
    body = 'CallMcpTool\nserver: llmwiki\ntoolName: wiki_search\n'
    assert session_used_wiki(meta, body=body) is True


def test_session_used_wiki_cursor_without_marker_is_false():
    meta = {"tools_used": ["GetMcpTools", "CallMcpTool", "Read"],
            "date": "2026-07-24"}
    body = 'CallMcpTool\nserver: github\ntoolName: issue_read\n'
    assert session_used_wiki(meta, body=body) is False


def test_session_used_wiki_negative():
    meta = {"tools_used": ["Read", "Grep", "Shell"], "date": "2026-07-01"}
    assert session_used_wiki(meta, body="no mcp here") is False


def test_daily_wiki_sessions_buckets_by_date():
    sessions = [
        ({"tools_used": ["mcp_llmwiki_wiki_query"], "date": "2026-07-12"}, ""),
        ({"tools_used": ["mcp__llmwiki__wiki_search"], "date": "2026-07-12"}, ""),
        ({"tools_used": ["Read"], "date": "2026-07-12"}, ""),
        ({"tools_used": ["CallMcpTool"], "date": "2026-07-24"},
         '"server": "llmwiki"'),
    ]
    assert daily_wiki_sessions(sessions) == {
        "2026-07-12": 2,
        "2026-07-24": 1,
    }


def test_daily_wiki_sessions_from_dir(tmp_path: Path):
    d = tmp_path / "sessions"
    d.mkdir()
    (d / "a.md").write_text(
        "---\ndate: 2026-07-12\ntools_used: [mcp__llmwiki__wiki_query]\n---\n",
        encoding="utf-8",
    )
    (d / "b.md").write_text(
        "---\ndate: 2026-07-12\ntools_used: [Read]\n---\n",
        encoding="utf-8",
    )
    assert daily_wiki_sessions_from_dir(d) == {"2026-07-12": 1}
