---
title: "State persistence"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-state-persistence, mcp-telemetry, usage-compact, vault-analytics, llmwiki-state, vault-state, analytics-pipeline, sync-lookback]
date: 2026-09-08
source_file: 
project: reference-state-persistence
model: 
last_updated: 2026-09-08
---
## Summary

This reference doc maps where llmwiki stores durable vault state beside `raw/`, `wiki/`, and `site/`: MCP usage under `usage/` (per-process JSONL, `rollup.json`, `daily.json`) versus pipeline and ops metadata in `llmwiki-state.json`. It explains append-on-tool-call logging, explicit `llmwiki usage --compact` folding, and how `llmwiki build` merges rollup, live JSONL, and session frontmatter for Analytics without double-counting. It also documents what is safe to delete, sync lookback GC for `sync.files` stamps only, and points to `llmwiki usage` and `migrate tools-used`.

## Key Claims

- MCP telemetry is append-only to `usage/mcp-<pid>-<start>.jsonl` per server process so concurrent MCP editors do not share one write lock.
- `llmwiki-state.json` holds synth queue, sync mtimes, cost estimate, Home pipeline snapshot, and `ops.*` stage stamps; MCP tools never write to it.
- `llmwiki usage --compact` folds retired monthly JSONL into `usage/rollup.json` and per-day buckets into `usage/daily.json`, then deletes the compacted JSONL files.
- `llmwiki build` computes `combined_totals` from rollup plus live JSONL not yet folded, and daily series from folded days plus a live overlay so heatmaps stay current without waiting for compact.
- When a durable sync lookback is configured, successful sync GCs that adapter’s `sync.files` entries older than the window; it does not delete `raw/` or alter queue, synth, quarantine, or ops.
- Deleting `usage/rollup.json` or `usage/daily.json` loses lifetime or historical daily MCP analytics respectively; compacted JSONL is only safe to delete after compact has run.

## Key Quotes

> "These files live beside `raw/`, `wiki/`, and `site/` — they are not merged into one blob. Each has a single job." — framing that vault persistence is split by responsibility, not one monolithic state file.

> "Append happens on every MCP tool call (best-effort; failures never break the call)." — telemetry is non-blocking for tool execution.

> "`llmwiki-state.json` follows a different lifecycle: sync, synth, build, and lint update it; it does not participate in MCP log folding." — separates pipeline state from usage compaction.

## Connections

- [[llmwiki]] (entity) — documents the vault-side persistence model for sync, synth, build, lint, and MCP usage.
  - fact: `llmwiki build` is the command that merges usage rollups, live JSONL, and session frontmatter into Analytics views.
- [[MCP Server]] (entity) — per-process `usage/mcp-*.jsonl` logs are written on every `wiki_*` tool call.
  - fact: MCP logging is append-only and isolated per PID/start file to avoid write contention.
- [[Static Site]] (concept) — derived `site/` is always safe to regenerate; Analytics and Home pipeline widgets read merged usage/state via build and `site/llmwiki-state.js`.
  - fact: A bare `llmwiki lint` refreshes `llmwiki-state.json` and the site data sidecar without rewriting HTML.
- [[Wiki Synthesis]] (concept) — synth queue and pipeline snapshot fields in `llmwiki-state.json` tie durable state to the synthesis pass.
- [[Adapters]] (concept) — sync lookback GC applies per-adapter `sync.files` mtimes when `filters.since` / `adapters.<name>.since` or CLI `--since` is set.
