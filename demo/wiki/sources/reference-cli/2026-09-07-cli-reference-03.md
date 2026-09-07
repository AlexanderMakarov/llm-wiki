---
title: "CLI reference (part 3/15: usage — MCP tool-usage telemetry vs synthesis cost (#26))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, mcp-telemetry, cli-reference, usage-tracking, session-adapters, caller-attribution]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-03.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This reference documentation describes three [[Codex CLI]] commands for telemetry and adapter management: `usage` (reporting MCP tool-usage against synthesis costs), `configure-sources` (interactive setup of session ingest adapters), and `adapters` (listing registered sources). The core innovation is per-process telemetry logging to avoid write contention, with caller attribution resolved via environment variables ([[Claude Code]]'s `CLAUDE_PROJECT_DIR`), MCP roots discovery, path heuristics, or fallback to unattributed. [[Cursor]] currently lacks zero-config attribution.

## Key Claims

- MCP telemetry is logged one JSON record per tool call to a per-process file (`mcp-<pid>-<start>.jsonl`) to eliminate write contention and keep telemetry off the hot path.
- [[Claude Code]] (≥v2.1.139) provides zero-config caller attribution by injecting `CLAUDE_PROJECT_DIR` into every stdio MCP server environment.
- [[Cursor]] currently provides no zero-config signal — `roots/list` returns "Method not found" despite advertising the capability — and falls back to path heuristics or `unknown`.
- Telemetry records are best-effort; failures never break tool calls. Opt-out with `LLMWIKI_MCP_TELEMETRY=0`.
- Daily aggregates in `usage/daily.json` persist across `--compact` operations, enabling Analytics activity heatmaps.
- Caller attribution is tried in order: `CLAUDE_PROJECT_DIR` env var → `roots/list` MCP call → path argument heuristic → unattributed.
- Records written by earlier versions carry no `caller_source` field and are read as unattributed regardless of their project name.

## Key Quotes

> "Each record carries `tool`, `query`, `hits` (`0` = a knowledge gap or noise; `null` = the tool can't report a count), `resp_bytes`, `duration_ms`, `caller_project`, `caller_source`, `server_pid`, `server_started`."

— Establishes the telemetry record schema that feeds usage reports and analytics.

> "Claude Code attributes every call with no setup, via `CLAUDE_PROJECT_DIR`. **Cursor** currently provides no zero-config signal — it advertises the `roots` capability but returns `Method not found` on the actual `roots/list` call."

— Documents the asymmetry in IDE integration maturity and workarounds.

> "Unattributed calls are counted in the totals but never presented as a project: they print as `(unattributed)` here and are excluded from the site's 'Heaviest project by MCP usage' card."

— Clarifies how unknowns are handled without breaking dashboards.

## Connections

- [[Codex CLI]] (tool) — the CLI commands documented here (`usage`, `configure-sources`, `adapters`).
  - fact: Three command-line interfaces for telemetry and adapter lifecycle management.
- [[Configuration]] (concept) — `configure-sources` writes to `config.json` and manages adapter enable/disable state.
  - fact: Interactive interview sets `filters.since` and `adapters.<name>` in gitignored config.
- [[Claude Code]] (editor) — provides zero-config caller attribution via `CLAUDE_PROJECT_DIR` environment injection.
  - fact: ≥v2.1.139 spawns one MCP server per session with stable workspace signal.
- [[Cursor]] (editor) — mentioned as lacking zero-config attribution despite roots capability advertisement.
  - fact: Currently falls back to path heuristics or unattributed until a fix ships.
- [[Observability]] (concept) — usage telemetry and analytics infrastructure for tracking MCP tool calls.
  - fact: Per-process JSONL files, daily rollups, and synthesis-cost comparison enable "is this wiki earning its spend?" questions.
- [[Configuration Reference]] (documentation) — cross-referenced for sync lookback settings and durable keys.

## Notes

- Contradicts assumption of uniform IDE support: [[Claude Code]] provides seamless zero-config attribution while [[Cursor]] advertises `roots/list` but returns "Method not found", requiring fallback heuristics.