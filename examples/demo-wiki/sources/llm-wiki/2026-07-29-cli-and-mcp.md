---
title: "CLI, sync, and MCP tools"
type: source
tags: [raw-doc, demo, llmwiki, mcp, session-transcript, llm-wiki, cli-interface, mcp-server, usage-analytics, document-ingestion, sync-workflow]
date: 2026-07-29
source_file: raw/docs/llm-wiki/cli-and-mcp.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

This document describes the primary user interfaces for the [[LLM Wiki]] system: a CLI command suite for orchestrating the session-to-site pipeline, and an [[MCP]] server providing editor-integrated tool access. The CLI offers six commands (`sync`, `synthesize`, `build`, `serve`, `add`, `lint`) at different stages of the content flow, while the MCP server mirrors core capabilities for editor-native use without context-switching. Tool usage is logged and analyzed to correlate synthesis effort with retrieval value.

## Key Claims

- The CLI provides six commands: `sync` converts agent sessions, `synthesize` runs LLM processing, `build` compiles static site HTML, `serve` runs a local HTTP server, `add` ingests external documents, and `lint` performs health checks
- The MCP server exposes seven tools—`wiki_query`, `wiki_search`, `wiki_read_page`, `wiki_list_sources`, `wiki_lint`, `wiki_dashboard`, and `wiki_add`—mirroring CLI operations for direct editor access
- Usage of each MCP tool is recorded to `usage/mcp-*.jsonl` and aggregated in a site Analytics page showing per-tool heatmaps and "payoff" views that correlate synthesis cost against retrieval demand

## Key Quotes

> "Each call can be recorded under `usage/mcp-*.jsonl`. The site Analytics page aggregates those records into MCP heatmaps, per-tool tables, and "payoff" views so you can see whether synthesis spend is earning retrievals."

This exemplifies a core design principle: instrument the entire interface to enable feedback loops where curators can measure which synthesis efforts drive the most actual retrieval value.

## Connections

- [[LLM Wiki]] — the project whose interfaces this document describes
- [[MCP]] — the protocol substrate enabling editor-native tool access and observability

## Contradictions

None identified.