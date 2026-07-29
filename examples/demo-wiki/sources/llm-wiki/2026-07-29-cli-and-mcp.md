---
title: "CLI, sync, and MCP tools"
type: source
tags: [raw-doc, demo, llmwiki, mcp, session-transcript, llm-wiki, cli-commands, mcp-server, analytics]
date: 2026-07-29
source_file: raw/docs/llm-wiki/cli-and-mcp.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

This document specifies the [[llm-wiki]] system's core CLI commands and MCP server interface. The CLI implements a four-stage pipeline (sync, synthesize, build, serve) to convert raw agent sessions and documents into published wiki content. The MCP server provides editor integration with tools for corpus discovery, page retrieval, maintenance, and ingestion, with per-call usage metrics tracked to measure tool ROI.

## Key Claims

- The operational workflow follows four stages: `llmwiki sync` (agent sessions → raw), `synthesize` (raw → wiki sources), `build` (sources → HTML), and `serve` (local preview)
- The MCP server exposes six tool families: discovery (`wiki_query`, `wiki_search`), retrieval (`wiki_read_page`, `wiki_list_sources`), maintenance (`wiki_lint`, `wiki_dashboard`), and ingestion (`wiki_add`)
- MCP tool usage is recorded per-call in `usage/mcp-*.jsonl` and aggregated in site analytics to generate per-tool heatmaps, usage tables, and cost-benefit ("payoff") ratios
- The CLI includes an `add` command for document ingestion with optional synthesis and build, a `lint` command for finding orphans and broken links, and a `serve` command for local preview

## Key Quotes

> "Convert new agent sessions into `raw/sessions/`" — the sync stage bridges from agent transcripts into the wiki's raw input layer

> "The site Analytics page aggregates those records into MCP heatmaps, per-tool tables, and 'payoff' views so you can see whether synthesis spend is earning retrievals." — usage analytics are designed to measure whether tool adoption justifies its infrastructure cost

## Connections

- [[llm-wiki]] — the system whose operational interface is documented here
- [[MCP]] — Model Context Protocol provides the editor integration mechanism
- [[Claude]] — typical host for the MCP server and `synthesize` backend
- [[synthesis]] — CLI stage that fills `wiki/sources/` from raw input
- [[Ollama]] — local alternative to the Claude synthesis backend
- [[GitHub Pages]] — Analytics on the public demo is fed by fixture MCP usage
