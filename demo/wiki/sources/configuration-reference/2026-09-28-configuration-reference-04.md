---
title: "Configuration Reference (part 4/8: Config file (config.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, config-json, sync-lookback, adapter-configuration, redaction-filtering]
date: 2026-09-28
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-28
---
## Summary

This session documents the complete schema and behavior of `config.json`, LLM Wiki's primary configuration file. It covers five main sections—filters (including the new sync lookback feature), redaction patterns, truncation limits, drop settings, and adapter configuration for Obsidian, Codex CLI, Gemini CLI, and OpenClaw. A significant portion details the sync lookback feature, which implements optional date-based filtering with a precise precedence order and includes early file pruning and garbage collection logic.

## Key Claims

- `config.json` must be copied from `examples/sessions_config.json` and placed at the repo root, where it is gitignored and auto-loaded by the converter.
- Sync lookback precedence (per adapter, highest first): CLI `--since` → adapter `YYYY-MM-DD` → adapter `"all"` → `filters.since` → unlimited; the value `"all"` is valid only on per-adapter keys.
- Sessions skipped due to lookback date filtering are **not** written into `llmwiki-state.json`, allowing them to be reconsidered when the time window is widened in future syncs.
- After a successful non-dry-run sync, coding-agent adapters with a durable lookback (config-file `since`, not CLI-only) have their `sync.files` entries garbage-collected if their stored mtime is before the lookback date.
- The `configure-sources` command is an interactive quiz that first prompts for a shared start date, then for each adapter prompts with a facts block, enable decision, path, and per-source date override.

## Key Quotes

> "config.json is gitignored. The converter auto-loads it if present at the repo root."

> "Precedence (per adapter, highest first): CLI `--since` → adapter `YYYY-MM-DD` → adapter `"all"` → `filters.since` → unlimited."

> "Sessions skipped only because of lookback are **not** written into `llmwiki-state.json` `sync.files`, so widening the window later can reconsider them on a normal sync."

## Connections

- [[llmwiki]] (entity) — the system whose configuration this documents
  - fact: Configuration auto-loads from `config.json` at the repo root if present.

- [[Adapters]] (entity) — each adapter subsection specifies how to ingest from different sources
  - fact: Supported adapters are Obsidian, Codex CLI, Gemini CLI, and OpenClaw, each with custom roots or vault paths.

- [[Obsidian]] (entity) — one of the configured adapters with vault ingestion support
  - fact: Obsidian adapter configuration includes `vault_paths`, `exclude_folders`, and `min_content_chars` settings.

- [[Codex CLI]] (entity) — one of the configured adapters for session ingestion
  - fact: Configuration specifies `roots` for session and project storage directories.

- [[Gemini CLI]] (entity) — one of the configured adapters
  - fact: Configuration points to `~/.gemini` as the root directory.

- [[Sync Lookback]] (concept) — a date-filtering feature that gates which sessions are ingested
  - fact: Supports shared (`filters.since`) and per-adapter overrides with early file pruning before loading.
  - fact: Lookback GC removes state entries for skipped sessions, enabling reconsideration on window widening.