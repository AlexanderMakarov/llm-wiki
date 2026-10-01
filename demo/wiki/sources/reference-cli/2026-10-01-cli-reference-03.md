---
title: "CLI reference (part 3/19: usage — MCP tool-usage telemetry vs synthesis cost (#26))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, mcp-telemetry, usage-tracking, caller-attribution, adapter-configuration]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This reference documents three CLI commands managing usage telemetry and adapter configuration in llmwiki. `usage` aggregates MCP tool-call logs (collected in per-process JSONL files) and persisted synthesis costs to answer whether the wiki justifies its compute expense. `configure-sources` interactively enables adapters and sets lookback dates; `adapters` lists registered adapters with enablement status. Caller attribution via `CLAUDE_PROJECT_DIR` (Claude Code), MCP `roots/list`, or path heuristics enables project-scoped cost analysis.

## Key Claims

- The `usage` command folds MCP telemetry and synthesis cost into a joint report; flags enable JSON output (`--json`), monthly rollup (`--compact`), and cost persistence via `usage/rollup.json` and daily series (`usage/daily.json`).
- MCP telemetry is collected to per-process JSONL files (`mcp-<pid>-<start>.jsonl`) and is best-effort, opt-out via `LLMWIKI_MCP_TELEMETRY=0`, and never blocks tool calls.
- Caller attribution tries three sources in order: `CLAUDE_PROJECT_DIR` (injected by [[Claude Code]] ≥v2.1.139), MCP `roots/list`, or path heuristic; unattributed calls are counted but excluded from site project cards.
- [[Claude Code]] achieves full zero-config attribution via `CLAUDE_PROJECT_DIR` injection; [[Cursor]] currently falls back to path heuristic or unattributed because `roots/list` returns "Method not found" and no workspace env var is injected.
- `--compact` folds past months into `usage/rollup.json` and deletes raw logs; daily series survives to power analytics heatmaps.
- `configure-sources` prompts for shared start date (default today−30) and per-adapter paths/dates, writing to gitignored `config.json`.
- Six MCP tools are tracked: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`.

## Key Quotes

> "Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the 'is this wiki earning its synthesis spend?' question is answerable at a glance."
— Core purpose of `usage`: quantifying ROI.

> "Several server processes run at once (one per editor session), so per-process files mean zero write contention and no lock on the hot path; telemetry never touches `llmwiki-state.json`."
— Design rationale for file isolation and performance.

> "Claude Code attributes every call with no setup, via `CLAUDE_PROJECT_DIR`. **Cursor** currently provides no zero-config signal — it advertises the `roots` capability but returns `Method not found` on the actual `roots/list` call, and injects no workspace env var — so its calls fall to the path heuristic where a path argument is present, else `unknown`, until it ships a fix."
— Documents asymmetry in editor client support.

## Connections

- [[llmwiki]] (entity) — the CLI tool being documented
  - fact: `usage` aggregates MCP telemetry with synthesis cost to track wiki ROI.
  - fact: `configure-sources` and `adapters` manage adapter ingest configuration.
- [[MCP Server]] (entity) — telemetry data source
  - fact: The server logs one JSON record per tool call to per-process files under `<vault>/usage/`, merged at read time to avoid write contention.
  - fact: Each record carries `tool`, `query`, `hits`, `resp_bytes`, `duration_ms`, `caller_project`, `caller_source`, `server_pid`, `server_started`.
- [[Adapters]] (concept) — two commands configure adapters
  - fact: `configure-sources` interactively enables adapters and sets per-adapter lookback dates.
  - fact: `adapters` command lists registered adapters with present/enabled status.
- [[Claude Code]] (entity) — demonstrates full caller attribution coverage
  - fact: Injects `CLAUDE_PROJECT_DIR` at ≥v2.1.139 into every stdio MCP server, enabling zero-config caller attribution.
- [[Cursor]] (entity) — demonstrates partial caller attribution coverage
  - fact: Advertises `roots/list` but returns "Method not found"; no workspace env var, so calls fall to path heuristic or unattributed.
- [[Observability]] (concept) — telemetry and monitoring
  - fact: Per-day MCP call totals in `usage/daily.json` feed analytics heatmaps on the site.
  - fact: Telemetry is best-effort; failures never break tool calls and can be opted out via `LLMWIKI_MCP_TELEMETRY=0`.
- [[Static Site]] (concept) — downstream analytics surface
  - fact: Daily series survives `--compact` to power "Heaviest project by MCP usage" card and Analytics pages.