---
title: "Upgrade guide (part 3/8: Unreleased — Claude control tags + session TOC (#229))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, upgrade-guide, synthesis-backends, cursor-agent-cli, adapter-lookback]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This upgrade guide (part 3 of 8) documents features and migration paths for [[llmwiki]] versions 2.1.0 through the unreleased release. Key changes include: Claude session control tag stripping to prevent CLI envelopes from appearing in wiki descriptions; new [[Cursor]] Agent CLI synthesis backend support; Home page pipeline state visualization; CLI command restructuring into six lifecycle sections; optional adapter lookback windows for date-based source filtering; and PyPI distribution as `llm-wiki-plus`.

## Key Claims

- Session sync now strips Claude Code local-command and command-name envelopes and background-task notifications to prevent them from polluting descriptions or prose content
- [[Cursor]] Agent CLI is supported as a synthesis backend via `synthesis.backend: "cursor_cli"` configuration, with cost estimates provided from a packaged pricing CSV
- The PyPI distribution is published as `llm-wiki-plus`, not `llm-wiki`, though the import and CLI remain `llmwiki`
- [[Adapters]] support optional `filters.since` configuration to limit lookback windows for date-based source filtering, with GC cleaning old `sync.files` stamps outside the window
- Session TOC appears as sticky left-column navigation below the hero for articles with ≥2 headings, using `max-width: 860px` collapse
- CLI commands were reorganized from flat names into six lifecycle sections, with renames like `synthesize` → `synth` and migrations grouped under the `migrate` subcommand

## Key Quotes

> "Convert now strips Claude Code local-command / slash-command envelopes… and background-task `[SYSTEM NOTIFICATION …]` / `<task-notification>` blocks so they never become `description:` or Conversation prose." — Session ingest improvements prevent IDE control structures from polluting wiki content.

> "`synthesis.backend` accepts `"cursor_cli"`: shells out to Cursor Agent CLI (`agent` / `cursor-agent` on `$PATH`) the same way `claude` uses `claude -p`." — New synthesis backend abstraction supports multiple LLM execution environments.

> "The published distribution is **`llm-wiki-plus`**… The import and CLI stay `llmwiki`." — PyPI packaging change affects installation but not internal APIs or user scripts.

## Connections

- [[llmwiki]] (entity) — the main wiki system; this document provides version-by-version migration guidance and feature documentation
  - fact: Session sync now strips Claude control tags to prevent IDE envelopes from appearing in descriptions.
  - fact: Multiple synthesis backends (Claude, [[Cursor]] Agent CLI, Ollama) are now pluggable via `synthesis.backend` configuration.
  
  - fact: `synthesis.backend: "cursor_cli"` enables Cursor Agent CLI with configurable model (default `composer-2.5`) and 180s timeout.
  - fact: Cost estimates use packaged `model_pricing.csv` for Cursor Composer and Grok pricing; no live API fetch.

- [[Configuration]] (entity) — multiple configuration and inheritance changes across versions
  - fact: `synthesis.backend` accepts `"cursor_cli"` with nested settings under `synthesis.cursor_cli`; flat fallback keys still work.
  - fact: Adapters support optional `filters.since` (YYYY-MM-DD or `"all"`) to set safe lookback windows before first sync.
  - fact: `adapters.cursor_ide` registry name changed from `adapters.cursor` to distinguish IDE Composer from CLI chats.

- [[Adapters]] (entity) — lookback window feature for safe date-limited source ingestion
  - fact: `llmwiki configure-sources` prompts for per-adapter start date and displays earliest available sessions.
  - fact: GC prunes `sync.files` stamps older than the lookback window on next successful sync; CLI `--since` does not trigger GC.
  - fact: Cursor IDE `sync.files` keys prefixed `cursor::` are rewritten to `cursor_ide::` on state load.

- [[Wiki Synthesis]] (concept) — synthesis backend abstraction now includes multiple LLM execution environments
  - fact: `build --synthesize` follows the active backend; `dummy` / unavailable backends skip the overview LLM.
  - fact: `--estimate` prices models from the active backend's published cost data.

- [[Claude Code]] (entity) — session ingest improvements for control structure stripping
  - fact: Local-command envelopes, command-name labels, and background-task notifications are stripped during sync conversion.
  - fact: Non-empty `<command-args>` are preserved on slash labels (e.g., `/implement-feature https://…`); injected skill markdown dumps are skipped.
  - fact: `/wiki-synthesize` slash command is retired in favor of `/wiki-synth` in v2.1.0.