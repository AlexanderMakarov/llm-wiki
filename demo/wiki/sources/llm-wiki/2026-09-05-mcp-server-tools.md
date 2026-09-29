---
title: "Expose the wiki over MCP so any agent can read it"
type: source
tags: [session, session-transcript, llm-wiki, claude, mcp-server, mcp-tools, cursor-integration, tool-schema, wiki-search]
date: 2026-09-05
source_file: raw/sessions/llm-wiki/2026-08-16T16-53-llm-wiki-mcp-server-tools.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The MCP server was extended with search, read-page, and query tools to enable Cursor (and any other MCP client) to read and query the wiki programmatically. A centralized kind vocabulary constant was introduced to keep the tool schema and handler synchronized, preventing vocabulary drift across the codebase.

## Key Claims

- The MCP server now exposes three tools: search, read-page, and query for wiki access
- The kind vocabulary is pinned to a single source constant to prevent drift between tool schema and handler definitions
- The MCP server is a stdio server compatible with Cursor, Claude Code, and Codex CLI
- The server functions independently from [[Adapters]] that read session stores
- All new functionality passes automated tests

## Key Quotes

> "I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph." — Design rationale for the three-tool architecture

> "I pointed both at the same constant so they cannot drift." — Vocabulary consistency strategy

> "it is a stdio server, so any MCP client can launch it. Cursor, Claude Code and Codex CLI all connect the same way. The server is a consumer surface and is entirely separate from the adapters that read session stores." — Server architecture and client compatibility

## Connections

- [[MCP Server]] (entity) — primary system extended with new tools and centralized vocabulary
  - fact: Now exposes search, read-page, and query tools for agents to access wiki pages and metadata
  - fact: Kind vocabulary is centralized to a single constant to keep schema and handler synchronized
- [[Cursor]] (entity) — motivating client for wiki accessibility without manual pasting
  - fact: Can now read the wiki through MCP server tools as a compatible stdio client
- [[Adapters]] (entity) — separate subsystem providing wiki data
  - fact: MCP server is architecturally separate from adapters that read session stores, functioning as a distinct consumer surface