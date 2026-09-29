---
title: "Configuration (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, config-json, redaction, filtering]
date: 2026-09-28
source_file: 
project: configuration
model: 
last_updated: 2026-09-28
---
## Summary
Part 1 of the configuration guide. Comprehensive documentation of llmwiki's config.json schema, covering session filtering by project/age/temp-cwd, optional path redaction for sanitizing sensitive data, text truncation limits, and per-adapter settings (e.g., Obsidian vault paths and exclusions). The converter auto-loads config.json (gitignored locally), defaulting to transparent real paths for private vaults.

## Key Claims
- config.json is gitignored so local settings stay private; the converter auto-loads it if present
- Username redaction can scrub paths like `/Users/<name>/…` to `/Users/USER/…` before writing to raw/
- exclude_headless filtering applies at both ingest and synthesis phases to skip automated SDK/CLI launches
- exclude_temp_cwd defaults OFF because git worktrees under /tmp often represent real work
- Per-adapter since dates can override shared sync lookback (YYYY-MM-DD or "all" for no date gate)
- CLI --since flag overrides all date-based filtering for a single run

## Key Quotes
> "the default `false` keeps real paths for a private vault"
— Shows the privacy-by-default model: redaction is opt-in, not forced

> "a git worktree under /tmp is often real work, so we don't silently drop it"
— Demonstrates careful design: exclude_temp_cwd defaults OFF to avoid hiding legitimate sessions

> "Skip automated / headless agent launches (default on). Claude: SDK entrypoint / promptSource; Cursor Agent CLI: subagentInfo or approvalMode=auto-review"
— Clarifies multi-agent filtering strategy across different platforms

## Connections
- [[llmwiki]] (entity) — the system whose configuration is documented
  - fact: config.json is gitignored and auto-loaded by the converter
- [[Adapters]] (entity) — per-adapter configuration allows vault-specific settings and filters
  - fact: Obsidian adapter can specify vault_paths, exclude_folders, and min_content_chars
- [[Wiki Synthesis]] (concept) — filtering and redaction rules shape which sessions ingest and what data sanitizes before synthesis
  - fact: exclude_headless and redaction settings apply at both ingest and synthesis phases