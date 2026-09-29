---
title: "MCP server — tool reference (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-mcp, tool-reference, wiki-search, json-rpc, search-consistency, tool-timeouts]
date: 2026-09-28
source_file: 
project: reference-mcp
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation specifies the six production tools exposed by the [[MCP Server]] over JSON-RPC 2.0: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, and `wiki_add`. It details each tool's purpose, arguments, return values, and behavioral guarantees. A central design principle is consistency between the web UI's quick search and the `wiki_search` API, both using identical matching rules and corpus walk. Tools enforce safeguards: `wiki_sync` requires dual confirmation before writing; `wiki_add` defaults to no synthesis and handles partial failures (write succeeds, build fails) gracefully. All operations support configurable wall-clock timeouts via `config.json`.

## Key Claims

- The [[MCP Server]] implements six production tools in `llmwiki/mcp/server.py`, enabling external clients (Claude Code, Cursor, Codex) to search, read, lint, sync, export, and add wiki content without shelling out to the CLI
- `wiki_search` supports three dispatch modes: `match` (literal substring search, mirrored by the site's ⌘K palette), `extract` (natural-language QA), and `filter` (metadata filtering on confidence, lifecycle, and tags)
- The [[Static Site]]'s quick search returns identical results in identical order as `wiki_search mode=match` because both use the same deterministic corpus walk, matching rules, and output caps (200 pages, 200 matching lines), but the site operates on the last-built corpus and never scans `raw/sessions/`
- `wiki_sync` defaults to dry-run and requires both `dry_run: false` and `confirm: true` to write changes; wall-clock timeout defaults to 120 seconds
- `wiki_add` is a proxy to CLI `llmwiki add` that defaults to writing raw docs and rebuilding the site without synthesizing source pages; long documents are chunked by the shared add orchestration (~7k chars per piece)
- When `wiki_add` succeeds at writing docs but fails on the post-add site build, it returns `isError: false` with the written paths and a warning—only genuine add failures set `isError: true`

## Key Quotes

> "Connect it from Claude Code, Cursor, Codex, or any MCP client so agents can search, read, lint, sync, export, and add to your wiki without shelling out to the CLI."

This statement establishes the core value proposition: standard MCP protocol enables programmatic wiki access without CLI invocation.

> "A term typed on the site and the same term given to `wiki_search` return the same retained pages in the same order."

This captures a critical design invariant—UI and API consistency in search behavior—ensuring that results are predictable across interfaces.

> "When the document lands under `raw/docs/` but the post-add site build fails, `wiki_add` still returns success (`isError: false`) with the written paths and a warning — reserve `isError` for genuine add failures."

This illustrates a graceful-degradation philosophy where write success is distinguished from downstream build success, prioritizing useful partial results.

## Connections

- [[MCP Server]] (entity) — the JSON-RPC 2.0 service component exposing wiki tools to external clients
  - fact: Implements six production tools in `llmwiki/mcp/server.py`
  - fact: Integrates with Claude Code, Cursor, Codex, and any MCP-compatible client via stdio
  - fact: Stores local-only telemetry under `<vault>/usage/`

- [[llmwiki]] (entity) — the wiki system these tools operate on
  - fact: Tools provide programmatic alternatives to CLI operations
  - fact: `wiki_add` shares orchestration with CLI `llmwiki add` (issue #273)

- [[Static Site]] (entity) — the published site whose search is synchronized with the MCP API
  - fact: Site's ⌘K palette uses identical matching rules and corpus walk as `wiki_search mode=match`
  - fact: Site enforces per-file (4 MiB) and aggregate (50 MiB) input limits during build
  - fact: Site caps output at 200 pages and 200 matching lines per query

- [[Wiki Synthesis]] (concept) — optional post-add synthesis for source pages
  - fact: `wiki_add` defaults to `synthesize: false`; users must explicitly request synthesis

- [[Wikilinks]] (concept) — cross-references validated by the `wiki_health` tool
  - fact: `wiki_health` returns the same JSON payload as `llmwiki lint --json`

## Contradictions

None identified.