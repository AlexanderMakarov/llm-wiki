---
title: "Expose the wiki over MCP so any agent can read it"
type: source
tags: [session, session-transcript, llm-wiki, claude, mcp-server, tool-schema, wiki-search, cursor-integration]
date: 2026-07-18
source_file: raw/sessions/llm-wiki/2026-07-18T16-53-llm-wiki-mcp-server-tools.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session exposed the wiki over [[MCP Server]] so external tools like [[Cursor]] can query it directly. The assistant added read-page and query tools to the server (search was already exposed), and unified page kind enumeration across the tool schema to prevent vocabulary drift.

## Key Claims

- The MCP server previously exposed only a search tool; read-page and query tools were added in this session
- Page kind enumeration was hardcoded in both the tool schema and a separate constant; these were unified to a single source to prevent drift
- The MCP server is implemented as a stdio-based service that any MCP client (e.g., [[Cursor]], [[Claude Code]], [[Codex CLI]]) can launch and consume
- The MCP server is a consumer-facing surface entirely separate from the adapters that read session stores

## Key Quotes

> "I want Cursor to be able to read the wiki without me pasting anything." — The user's motivating use case

> "The tool schema advertises the page kinds a caller can filter by, and that list was hardcoded separately from the schema module. I pointed both at the same constant so they cannot drift." — The vocabulary unification solution

## Connections

- [[MCP Server]] — the primary service being implemented to expose the wiki
- [[Cursor]] — the IDE being integrated as an MCP client
- [[Claude Code]] — another MCP client mentioned in the session