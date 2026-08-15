---
title: "Configuration (part 2/2: CLI flags)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, cli-flags, error-handling, theming]
date: 2026-08-10
source_file: 
project: configuration
model: 
last_updated: 2026-08-11
---
## Summary

This documentation covers the CLI flags and configuration system for [[llmwiki]], the LLM session ingestion and wiki-building tool. It documents all five subcommands (sync, build, serve, init, adapters) with their flags and options, adapter-specific configuration for Claude Code and Obsidian with multi-vault support, `.llmwikiignore` patterns for filtering, and CSS-based theme customization via build-time variables.

## Key Claims

- The `sync` command allows filtering by adapter name, date, project substring, and session age, with graceful per-file error handling by default (errors logged, not fatal) and optional hard failure via `--fail-on-errors` for CI pipelines
- No `sync --dry-run` exists; users should use `add --dry-run` for intake previews or `sync --status` for status inspection before running sync
- The Obsidian adapter supports multiple vault paths (checked in priority order) and can exclude specific folders like `.obsidian` and `Templates`, plus skip files smaller than a configurable `min_content_chars` threshold
- `.llmwikiignore` uses gitignore-style patterns to skip whole projects, date ranges, or specific sessions during sync
- Theme colors are hardcoded in `llmwiki/build.py` under the CSS `:root` block; dark-mode variants auto-derive unless explicitly overridden
- Codex CLI adapter (v0.1) is currently a stub; full parsing configuration is planned for v0.2

## Key Quotes

> "Per-file conversion errors do not fail the run by default: each one is counted in the summary, recorded in `llmwiki-state.json` quarantine entries, and visible via `llmwiki sync --status`, while the rest of the corpus still converts."

This reflects the tool's resilience design: errors are visible but non-fatal, allowing partial corpus ingestion when some sessions fail.

> "There is **no** `sync --dry-run` — use `add --dry-run` for document intake previews, or inspect with `sync --status` / `synth --estimate`."

This establishes the mental model: `add` is for previewing raw input, `sync --status` for checking state before running, not a dedicated dry-run mode.

## Connections

- [[llmwiki]] — the tool whose configuration this documents
- Adapter configuration — covers Claude Code store location, Obsidian multi-vault paths and exclusion rules, and Codex CLI stub status