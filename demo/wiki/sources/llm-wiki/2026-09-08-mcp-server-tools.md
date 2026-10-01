---
title: "Expose the wiki over MCP so any agent can read it"
type: source
tags: [session, session-transcript, llm-wiki, claude, mcp-server, mcp-tools, cursor-integration, tool-schema, wiki-search, kind-vocabulary]
date: 2026-09-08
source_file: raw/sessions/llm-wiki/2026-08-16T16-53-llm-wiki-mcp-server-tools.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Added search, read-page, and query tools to the [[MCP Server]] to enable any MCP client (including [[Cursor]]) to read the wiki directly without manual copy-paste. A key technical decision unified the page kinds vocabulary to a single constant, preventing the tool schema definition from drifting out of sync with the handler implementation.

## Key Claims

- The [[MCP Server]] now exposes three tools: `search`, `read-page`, and `query` for programmatic wiki access.
- Page kinds vocabulary is pinned to a single constant that both tool schema and handler reference, preventing inadvertent divergence.
- The MCP server is a stdio-based architecture compatible with any MCP client (Cursor, [[Claude Code]], [[Codex CLI]]) without client-specific logic.
- The `query` tool can walk the [[Knowledge Graph]] to answer user questions about the wiki.
- The [[MCP Server]] is architecturally separate from adapters and session store readers; it is a consumer surface only.

## Key Quotes

> "I want Cursor to be able to read the wiki without me pasting anything." — User's goal to enable frictionless wiki access in the IDE.

> "The MCP server already exposed a search tool. I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph." — Summary of the three-tool solution.

> "the tool schema advertises the page kinds a caller can filter by, and that list was hardcoded separately from the schema module. I pointed both at the same constant so they cannot drift." — Key technical decision to avoid schema duplication.

> "it is a stdio server, so any MCP client can launch it. Cursor, Claude Code and Codex CLI all connect the same way." — Clarification that the MCP server is client-agnostic.

## Connections

- [[MCP Server]] (entity) — Extended with three query tools; is the central integration point for wiki access via MCP.
  - fact: Now exposes search, read-page, and query tools.
  - fact: Uses stdio transport compatible with any MCP client.

- [[Cursor]] (entity) — Primary user-facing client; motivation for this session.
  - fact: Can now read the wiki directly via MCP without copy-paste workflow.

- [[Claude Code]] (entity) — Also uses the same stdio MCP server interface.
  - fact: Benefits from unified page kinds vocabulary and tool consistency.

- [[Codex CLI]] (entity) — Also connects to the MCP server using the same protocol.

- [[Knowledge Graph]] (concept) — The query tool walks the graph to answer questions.
  - fact: Query tool implementation relies on graph traversal semantics.

- [[Wikilinks]] (concept) — Related to page structure and graph navigation.

- [[Frontmatter]] (concept) — Page kinds are advertised in tool schema for filtering.
  - fact: Kind vocabulary unified so tool schema and handler remain in sync.