"""llmwiki MCP server.

Exposes llmwiki operations as Model Context Protocol (MCP) tools that any
MCP-capable client (Claude Desktop, Claude Code, Codex, Cline, Cursor, ChatGPT
desktop, etc.) can call directly.

Six production tools (#196):

    - wiki_search(mode, …)       — unified match / extract / filter search
    - wiki_read_page(path)       — read one page (path-traversal guarded)
    - wiki_health(rules?, min_refs?) — lint JSON + headline totals
    - wiki_sync(dry_run?, confirm?)  — trigger the converter
    - wiki_export(format)        — return any AI-consumable export
    - wiki_add(url | path | content) — ingest one source into raw/docs/

Protocol: Model Context Protocol, stdio transport, JSON-RPC 2.0.
See the MCP spec at: https://modelcontextprotocol.io/
Full reference: docs/reference/mcp.md

Run with:

    python3 -m llmwiki.mcp
"""

from __future__ import annotations

from llmwiki.mcp.server import main

__all__ = ["main"]
