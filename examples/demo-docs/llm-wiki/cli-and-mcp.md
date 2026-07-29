---
title: "CLI, sync, and MCP tools"
slug: cli-and-mcp
project: llm-wiki
type: source
tags: [raw-doc, demo, llmwiki, mcp]
date: 2026-07-29
source: examples/demo-docs/llm-wiki/cli-and-mcp.md
---

# CLI, sync, and MCP tools

## Day-to-day CLI

| Command | Role |
|---|---|
| `llmwiki sync` | Convert new agent sessions into `raw/sessions/` |
| `llmwiki synthesize` | Fill `wiki/sources/` from raw sessions/docs (Claude, Ollama, or dummy) |
| `llmwiki build` | Compile `site/` HTML + Analytics |
| `llmwiki serve` | Local HTTP server for the site |
| `llmwiki add <url\|file>` | Ingest a document into `raw/docs/` (optional synth + build) |
| `llmwiki lint` | Orphans, broken links, stale pages |

## MCP server

Editors can attach the llmwiki MCP server and call tools such as:

- `wiki_query` / `wiki_search` — find answers and grep the corpus
- `wiki_read_page` — load one page
- `wiki_list_sources` — inventory raw sessions
- `wiki_lint` / `wiki_dashboard` — health checks
- `wiki_add` — ingest a source through the same path as the CLI

Each call can be recorded under `usage/mcp-*.jsonl`. The site Analytics page aggregates those records into MCP heatmaps, per-tool tables, and “payoff” views so you can see whether synthesis spend is earning retrievals.
