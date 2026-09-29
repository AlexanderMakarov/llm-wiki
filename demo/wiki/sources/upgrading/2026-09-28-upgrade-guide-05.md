---
title: "Upgrade guide (part 5/8: v1.5.0 — Analytics layout + CallMcpTool migration)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, state-snapshot, path-redaction, callmcptool-migration, cli-build]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

The v1.5.0 upgrade guide documents required and optional steps for upgrading llm-wiki. The mandatory step is running `llmwiki build` to restore local working directory paths in site indices and backfill state snapshots with `synth.pipeline`. Optional steps include migrating CallMcpTool entries from agent sessions and deterministically redacting encoded paths in raw documents for publication safety.

## Key Claims

- Upgrading to v1.5.0 requires `llmwiki build` to regenerate site indices with restored local working directory paths and Analytics layout updates
- `llmwiki build` one-shot backfills `synth.pipeline` in state files when missing (from v1.4.0 state), filling the Home State widget without needing a separate `synth --estimate`
- `llmwiki migrate tools-used` expands CallMcpTool entries in raw sessions when source agent files still exist; rows are skipped safely when sources have expired (typically ~30 days)
- Agent session stores retain transcripts only ~30 days, making `llmwiki sync --force` inappropriate for path redaction migration
- Deterministic `llmwiki migrate raw-redaction` rewrites encoded paths without LLM invocation or token cost
- Site rebuild adds a **Cwd** column to the sessions index table for usable local `cd … && claude --resume …` commands

## Key Quotes

> "build also one-shot backfills `synth.pipeline` in `llmwiki-state.json` / `llmwiki-state.js` when that key is missing (state last written by v1.4.0). That fills the Home **State** widget without a separate `synth --estimate`. The refresh is local-only (no API / no tokens) and runs only on a shape mismatch — later builds skip it once the snapshot exists."

- Explains why build is required and what state update accomplishes without cost.

> "Agent stores usually retain transcripts only ~**30 days** (Claude Code retention; Cursor similar). Older sessions in `raw/` often have **no** source file left to re-convert from — force-sync silently skips or fails those rows while still looking like 'migration work'."

- Justifies why force-sync is inappropriate for path migration despite appearing to be a valid approach.

> "The path-string rewrite above is enough."

- Emphasizes that deterministic path redaction alone is sufficient for migration needs without re-synthesizing content.

## Connections

- [[llmwiki]] (entity) — The wiki system undergoing v1.5.0 upgrade; guides document required and optional post-upgrade steps.
  - fact: `llmwiki build` now backfills `synth.pipeline` in state files when missing from v1.4.0.
  - fact: Build regenerates site indices with restored local working directory paths.

- [[Configuration]] (entity) — Username redaction settings are auto-detected by v1.5.0; manual config edit not required unless user enables `redaction.redact_username: true`.
  - fact: #56 re-autodetects redaction config after vault setup, eliminating need for manual placeholder clearing.

- [[State Snapshot]] (concept) — v1.5.0 introduces one-shot backfill of `synth.pipeline` during `llmwiki build` to populate Home State widget without requiring separate `synth --estimate`.
  - fact: Backfill is local-only and runs only when state shape changes; subsequent builds skip it.
  - fact: Refresh is triggered by sync, add, and estimate commands when content changes.

- [[Path Redaction]] (concept) — Deterministic migration tool for rewriting dash-encoded usernames in raw session paths; essential for vaults intended for publication, optional for private vaults.
  - fact: Migrator requires no LLM and costs zero tokens.
  - fact: Tool safely skips sessions beyond 30-day agent transcript retention window.

## Contradictions

- N/A (no contradictions with existing wiki content detected)