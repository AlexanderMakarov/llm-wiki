---
title: "Expose the wiki over MCP so any agent can read it"
type: source
tags: [session, session-transcript, llm-wiki, claude, mcp-server, tool-schema, wiki-api]
date: 2026-08-15
source_file: raw/sessions/llm-wiki/2026-08-15T16-53-llm-wiki-mcp-server-tools.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Extended the MCP server with read-page and query tools (search pre-existed) to enable any MCP client, including Cursor, to read and traverse the wiki graph without copy-paste workflows. Unified the tool schema's page kind vocabulary to a single constant, preventing drift between schema and runtime filters.

## Key Claims

- The MCP server now exposes three tools: search, read-page, and query—allowing agents to search, open specific pages, and traverse the knowledge graph.
- The tool schema's page kind vocabulary was unified to a single constant to prevent divergence between the schema definition and runtime filtering logic.
- The MCP server is a stdio-based server compatible with any MCP client (Cursor, Claude Code, Codex CLI).
- The MCP server is architecturally separate from the session store adapters that feed it data.

## Key Quotes

> "I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph." — Explains the three-tool interface

> "I pointed both at the same constant so they cannot drift." — Describes the critical vocabulary unification

> "Cursor, Claude Code and Codex CLI all connect the same way. The server is a consumer surface and is entirely separate from the adapters that read session stores." — Clarifies the MCP server's role in the architecture

## Connections

- [[llmwiki]] (system) — the wiki being exposed via MCP
  - fact: Now remotely accessible to any MCP-compatible client without manual copy-paste
- [[MCP Server]] (component) — implements read-page, query, and search tools
  - fact: Tool vocabulary schema unified to a single constant to prevent divergence
- [[Cursor]] (tool) — primary motivating use case
  - fact: Can now read the wiki through the MCP server interface
- [[Claude Code]] (tool) — MCP client with full wiki access
  - fact: Connects via stdio like any other MCP client
- [[Codex CLI]] (tool) — shares the same MCP interface
  - fact: Works identically to Claude Code and Cursor over the same server

## Contradictions

(None identified.)