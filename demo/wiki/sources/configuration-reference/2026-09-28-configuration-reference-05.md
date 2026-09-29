---
title: "Configuration Reference (part 5/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, synthesis-backend, data-redaction, sync-filters, adapter-settings]
date: 2026-09-28
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-28
---
## Summary

Part 5 of the Configuration Reference documents the schema and defaults for [[llmwiki]] settings governing ingest filters, data redaction, output truncation, scheduling, and synthesis backend selection. It specifies how to exclude headless sessions (to prevent synthesis feedback loops), override sync lookback per adapter, select synthesis backends (dummy/ollama/claude/cursor_cli), and configure cost optimizations like stripping agent scaffolding and adjusting model effort.

## Key Claims

- The `exclude_headless` filter applies at both ingest and synthesis stages to prevent automated agents from creating feedback loops (default: `true`).
- Nested configuration keys (e.g., `synthesis.claude.model`) override flat keys (e.g., `synthesis.claude_model`), and per-adapter `since` values override the global `filters.since` unless set to `"all"`.
- The `synthesis.claude.lean=true` default strips agent scaffolding (tool schemas, MCP, skills, system prompt) from each Claude call, reducing synthesis cost approximately 9× per page.
- Extended thinking on Claude is billed as output tokens at ~5× the input rate; Haiku produces ~5,753 output tokens/page at default effort vs. 1,609 at `low`.
- Synthesis backend can be overridden per-run via CLI flag `--backend <name>` without modifying config; backends include dummy, ollama, claude (synchronous), and cursor_cli.

## Key Quotes

> "Skip sessions younger than this (prevents reading mid-write)" — `filters.live_session_minutes` guards against incomplete mid-write session data from being ingested.

> "Prevents the synthesis feedback loop. Applies at **both** ingest and synthesis." — `exclude_headless` is critical for preventing automated/headless launches (Claude SDK, Cursor Agent CLI) from creating recursive synthesis chains.

> "Strip agent scaffolding (tool schemas, MCP, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured." — `synthesis.claude.lean=true` is the key cost optimization, quantified by measurement.

> "Extended thinking is billed as output at ~5x input; on Haiku it was 5,753 output tokens/page at the default vs 1,609 at `low`." — concrete impact of `synthesis.claude.effort` tuning on token cost.

## Connections

- [[llmwiki]] (entity) — the application being configured
  - fact: Configuration schema covers ingest filters, redaction, truncation, synthesis backend selection, and adapter-specific overrides.

- [[Adapters]] (entity) — adapter-specific configuration overrides
  - fact: Per-adapter `since` and other settings can override global defaults; `adapters.<name>` allows `since` override per ingestion source.

- [[Wiki Synthesis]] (concept) — synthesis backend selection and tuning
  - fact: Backend choice (dummy/ollama/claude/cursor_cli), model selection, timeout, concurrency, and effort all control synthesis cost and quality.

- [[MCP Server]] (entity) — scaffolding removed during synthesis
  - fact: `synthesis.claude.lean=true` strips MCP, tool schemas, and agent system prompt to reduce token usage.

- [[Ollama]] (entity) — one of the available synthesis backends
  - fact: `synthesis.ollama` section configures model name, base URL, per-request timeout, and exponential-backoff retry count.

- [[GitHub Actions]] (entity) — scheduling integrates with configuration
  - fact: `schedule.build` and `schedule.lint` control when `/wiki-build` and `/wiki-lint` are triggered (on-sync/daily/weekly/manual/never).

## Contradictions

None identified.