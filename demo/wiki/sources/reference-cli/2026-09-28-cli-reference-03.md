---
title: "CLI reference (part 3/19: usage — MCP tool-usage telemetry vs synthesis cost (#26))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, mcp-telemetry, caller-attribution, synthesis-cost, cli-reference]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation (part 3 of 19) covers three CLI commands: `usage` (reporting MCP telemetry against synthesis cost), `configure-sources` (interactive adapter setup), and `adapters` (listing adapter status). It details how the [[MCP Server]] logs per-process telemetry files to avoid write contention, and explains caller attribution mechanisms—notably [[Claude Code]]'s zero-config `CLAUDE_PROJECT_DIR` injection versus [[Cursor]]'s current limitations falling back to path heuristics.

## Key Claims

- The MCP server logs one JSON record per tool call to a per-process file under `<vault>/usage/` to eliminate write contention and keep telemetry off the hot path.
- Claude Code (≥ v2.1.139) auto-injects `CLAUDE_PROJECT_DIR` into every stdio MCP server with zero config, providing stable per-caller attribution; it spawns one server per session.
- Cursor currently advertises `roots` capability but returns `Method not found` on `roots/list` calls and injects no workspace env var, so its callers fall back to path heuristics or `unknown` until a fix ships.
- The `usage` command answers "is this wiki earning its synthesis spend?" by comparing MCP telemetry totals to synthesis cost persisted in state.
- Unattributed calls are excluded from the site's "Heaviest project by MCP usage" card.
- The `configure-sources` command is an interactive interview that writes adapter enable/path/start-date to `config.json`.

## Key Quotes

> "Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the "is this wiki earning its synthesis spend?" question is answerable at a glance."
— Core value proposition: the `usage` command provides ROI analysis at a glance.

> "Claude Code sets `CLAUDE_PROJECT_DIR` (≥ v2.1.139) into every stdio MCP server — zero config — and spawns one server per session, so it is a stable per-caller signal available at the first call."
— Explains why Claude Code has plug-and-play caller attribution without setup.

> "Cursor currently provides no zero-config signal — it advertises the `roots` capability but returns `Method not found` on the actual `roots/list` call, and injects no workspace env var — so its calls fall to the path heuristic where a path argument is present, else `unknown`, until it ships a fix."
— Documents current limitation in Cursor requiring client-side fix.

## Connections

- [[MCP Server]] (entity) — Server that logs telemetry and exposes six tools for wiki operations.
  - fact: Logs one JSON record per tool call to per-process files to avoid write contention.
  - fact: Each record includes tool, query, hits, resp_bytes, duration_ms, caller_project, caller_source, server_pid.
- [[Claude Code]] (entity) — Editor client with zero-config caller attribution via environment injection.
  - fact: Auto-injects `CLAUDE_PROJECT_DIR` (≥ v2.1.139) into every stdio MCP server.
  - fact: Spawns one server per session, providing stable per-caller signal.
- [[Cursor]] (entity) — Editor client currently limited in caller attribution; falls back to path heuristics.
  - fact: Advertises `roots` capability but returns `Method not found` on `roots/list` calls.
  - fact: Injects no workspace env var, requiring eventual client-side fix.
- [[Adapters]] (entity) — Ingestion sources configured via `configure-sources` and `adapters` commands.
  - fact: `configure-sources` is an interactive interview for adapter enable, path, and start-date.
  - fact: `adapters` command lists registered adapters with present and enabled status.
- [[llmwiki]] (entity) — Project whose CLI tools and MCP telemetry system are documented here.
- [[Wiki Synthesis]] (concept) — The `usage` command evaluates synthesis ROI by comparing telemetry to cost.
  - fact: `usage/daily.json` stores per-day MCP call totals for Analytics activity heatmaps.
  - fact: Unattributed calls are excluded from "Heaviest project by MCP usage" card.

## Contradictions

None identified.