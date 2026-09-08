---
title: "Expose the wiki over MCP so any agent can read it"
type: source
tags: [session, session-transcript, llm-wiki, claude, mcp-server, mcp-tools, cursor-integration]
date: 2026-08-16
source_file: raw/sessions/llm-wiki/2026-08-16T16-53-llm-wiki-mcp-server-tools.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

Added search, read-page, and query tools to the [[MCP Server]] to enable [[Cursor]], [[Claude Code]], and [[Codex CLI]] to access wiki content directly without copy-paste. Unified the page kinds vocabulary in a single constant to prevent schema-implementation drift.

## Key Claims

- The [[MCP Server]] exposes three tools: search (find pages), read-page (fetch specific page), and query (traverse the knowledge graph)
- Page kinds filter vocabulary is centralized in a single constant, preventing divergence between tool schema and runtime implementation
- The [[MCP Server]] functions as a stdio server compatible with any MCP-compliant client, including [[Cursor]], [[Claude Code]], and [[Codex CLI]]
- The [[MCP Server]] is architecturally independent of vault adapters, consuming already-ingested content rather than reading session stores directly

## Key Quotes

> "I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph." — Describes the new tools enabling programmatic wiki access patterns

> "I pointed both at the same constant so they cannot drift." — Explains the vocabulary pinning decision to maintain consistency between schema definition and usage

> "The server is a consumer surface and is entirely separate from the adapters that read session stores." — Clarifies architectural separation between the MCP exposure layer and vault ingestion

## Connections

- [[MCP Server]] (system) — Exposes wiki as an MCP resource for external tools and agents
  - fact: Implements search, read-page, and query tools for wiki access
  - fact: Page kinds vocabulary is unified in a single constant
- [[Cursor]] (tool) — IDE client that can read wiki via [[MCP Server]]
  - fact: Primary motivating use case for MCP server exposure
- [[Claude Code]] (tool) — Also connects to [[MCP Server]] as an MCP client
- [[Codex CLI]] (tool) — CLI that connects to [[MCP Server]] alongside GUI clients
- [[Knowledge Graph]] (concept) — MCP query tool provides semantic access to graph structure
  - fact: Query tool enables traversal of relationships between wiki topics
- [[Adapters]] (system) — Architecturally separate consumption layer; [[MCP Server]] consumes ingested vault
  - fact: MCP server does not directly read session stores or ingest vault content
