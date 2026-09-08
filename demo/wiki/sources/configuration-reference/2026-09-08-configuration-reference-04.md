---
title: "Configuration Reference (part 4/8: Config file (config.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, config-json, sync-lookback, session-filters, redaction, adapter-paths]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the configuration reference documents the root `config.json` schema (filters, redaction, truncation, `drop_thinking_blocks`, and per-adapter roots) and explains **sync lookback**: shared `filters.since`, per-adapter `adapters.<name>.since` (including `"all"`), and CLI `--since` precedence. It also covers how lookback is applied during sync (early prune, no `sync.files` entries for lookback-only skips, optional lookback GC for coding-agent adapters), the end-of-sync hint toward `configure-sources`, and the interactive quiz order (shared start date first, then each source).

## Key Claims

- `config.json` is gitignored; the converter auto-loads it from the repo root when present (typically copied from `examples/sessions_config.json`).
- For each adapter, effective lookback precedence is: CLI `--since` → adapter `YYYY-MM-DD` → adapter `"all"` → `filters.since` → unlimited; `"all"` is only valid on the per-adapter key, and invalid date strings exit with code **2**.
- Sessions skipped solely because of lookback are **not** recorded in `llmwiki-state.json` under `sync.files`, so widening the window later can pick them up on a normal sync.
- After a successful non-dry-run sync, lookback GC removes `sync.files` keys for **coding-agent** adapters with a **durable** lookback (config-based, not one-run CLI `--since`) when stored mtime is before the lookback; it does not delete `raw/` or GC non–AI-session intake (e.g. Obsidian).
- `llmwiki configure-sources` interviews **shared start date first** (default Enter = today−30 or stored date), then each source with a facts block, enable prompt semantics (`[Y/n]` vs `[y/N]`), path, and per-source start date (Enter inherits shared).

## Key Quotes

> "Unset shared and per-adapter keys mean **unlimited** — same as today's default." — Documents default sync behavior when no `since` keys are set (#192 context).

> "sessions skipped only because of lookback are **not** written into `llmwiki-state.json` `sync.files`" — Explains why widening lookback can reconsider previously skipped sessions without stale state blocking them.

## Connections

- [[llmwiki]] (entity) — Central product whose sync pipeline reads `config.json` and applies filters, redaction, truncation, and adapter roots.
  - fact: Bare `llmwiki sync` can be gated by optional absolute-date lookback without changing unlimited default when keys are absent.
- [[Adapters]] (concept) — `adapters` block configures Obsidian vault paths, Codex CLI roots, Gemini CLI roots, and OpenClaw roots plus per-adapter `since`.
  - fact: Per-adapter `since` can override shared `filters.since` or opt a single source out with `"all"`.
- [[Obsidian]] (entity) — Optional adapter with `vault_paths`, `exclude_folders`, and `min_content_chars`; lookback GC explicitly does not apply to notes/export intake (`is_ai_session: false`).
- [[Codex CLI]] (entity) — Adapter entry uses `roots` under `~/.codex/sessions` and `~/.codex/projects`.
- [[Gemini CLI]] (entity) — Adapter entry uses `roots` under `~/.gemini`.
- [[Wiki Synthesis]] (concept) — Lookback GC is scoped to not touch queue, synth, quarantine, or ops state—only durable lookback cleanup on `sync.files` for coding agents.
