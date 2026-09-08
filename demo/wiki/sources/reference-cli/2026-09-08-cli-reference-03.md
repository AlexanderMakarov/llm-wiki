---
title: "CLI reference (part 3/15: usage — MCP tool-usage telemetry vs synthesis cost (#26))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, mcp-telemetry, synthesis-cost, usage-command, caller-attribution, configure-sources, usage-rollup]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents three CLI areas: **`usage`**, which merges per-process MCP tool-call JSONL under `<vault>/usage/` with synthesis cost from state so spend vs MCP benefit is visible; **`configure-sources`**, an interactive pass that sets shared and per-adapter sync lookback and enablement in gitignored `config.json`; and **`adapters`**, a read-only registry of which session stores exist on disk and whether bare `sync` includes them. It also specifies caller attribution (`caller_project` / `caller_source`) for telemetry, daily series persistence for Analytics after `--compact`, and known client gaps (notably **Cursor** vs **Claude Code**).

## Key Claims

- `llmwiki usage` aggregates MCP telemetry from `<vault>/usage/mcp-<pid>-<start>.jsonl` and prints totals alongside synthesis cost persisted in state (#26).
- MCP telemetry uses one JSONL file per server process to avoid write contention; failures are best-effort and opt-out is `LLMWIKI_MCP_TELEMETRY=0`.
- Caller resolution order is `project-dir-env` → `client-root` → `path` → `unattributed`; all path-based sources share `slugs.project_slug_from_abs_path` with session ingestion.
- Claude Code (≥ v2.1.139) attributes every MCP call via injected `CLAUDE_PROJECT_DIR`; Cursor has no zero-config signal because `roots/list` returns “Method not found” and no workspace env var is injected.
- Unattributed calls appear as `(unattributed)` in the CLI report and are excluded from the static site’s “Heaviest project by MCP usage” card.
- `usage --compact` folds whole past months into `usage/rollup.json`, deletes raw logs, and `usage/daily.json` preserves per-day totals for Analytics heatmaps (#52).
- `configure-sources` merge-writes only `filters.since`, `adapters.<name>.since`, enable flags, and paths; `--yes` skips the interview with no config writes.
- `llmwiki adapters` lists `present` (store on disk) and `enabled` (included on next bare `sync`); one-off sync uses `sync --adapter <name>`.

## Key Quotes

> "Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the 'is this wiki earning its synthesis spend?' question is answerable at a glance." — purpose of `usage`

> "Several server processes run at once (one per editor session), so per-process files mean zero write contention and no lock on the hot path; telemetry never touches `llmwiki-state.json`." — storage design

> "The server's own `os.getcwd()` is never used: a client may launch the server anywhere (Claude Code's desktop app uses `$HOME`), so it is unrelated to the caller's project." — why cwd is not attribution

> "Scope is MCP calls only — `file://` static-site browsing stays untracked." — telemetry boundary

## Connections

- [[llmwiki]] (entity) — CLI commands documented here are core product surface for vault ops and cost visibility.
  - fact: `usage`, `configure-sources`, and `adapters` are first-class subcommands with flags tied to vault paths and state files.
- [[MCP Server]] (entity) — six live tools log one JSON record per call; see separate MCP reference for tool names and #196 migrations.
  - fact: Telemetry records include `tool`, `query`, `hits`, `resp_bytes`, `duration_ms`, and caller fields without blocking tool execution.
- [[Claude Code]] (entity) — default high-quality caller attribution for MCP usage breakdown by project.
  - fact: `CLAUDE_PROJECT_DIR` in the MCP server environment yields `caller_source: project-dir-env` with no user setup.
- [[Cursor]] (entity) — contrib/client gap: MCP usage often `unattributed` or path-heuristic until roots/env support ships.
  - fact: Advertised `roots` capability fails on `roots/list`; no workspace env injection documented here.
- [[Adapters]] (entity) — `configure-sources` and `adapters` govern which session stores sync on bare `sync`.
  - fact: Interview writes `adapters.<name>` and shared `filters.since`; listing shows present vs enabled separately from `sync --adapter`.
- [[Static Site]] (entity) — Analytics consumes `usage/daily.json` and project-weighted MCP cards; not raw CLI-only output.
  - fact: Daily series survives `--compact`; unattributed MCP volume is omitted from “Heaviest project by MCP usage.”
- [[Wiki Synthesis]] (concept) — synthesis cost side of the usage report answers ROI against MCP retrieval/write activity.
  - fact: `--state-file` selects where synthesis-cost estimate is read for pairing with `consumption` totals.
