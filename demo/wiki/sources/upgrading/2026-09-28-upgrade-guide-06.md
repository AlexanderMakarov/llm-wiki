---
title: "Upgrade guide (part 6/8: Downgrading is guarded (#29))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, schema-versioning, state-migration, queue-management]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This upgrade guide chapter (part 6 of 8) documents schema versioning guards and major migration paths for llmwiki. The central change is v1.4.0's hard cutover to unified state file architecture, queue-based synthesis, and Python ≥ 3.12 requirement. It covers downgrade protection mechanisms, state file consolidation, and migration paths for legacy dotfiles and in-clone wikis.

## Key Claims

- As of issue #29, `sync` refuses to run when the vault's `llmwiki-state.json` was written by a newer schema version, preventing silent data loss from downgrade attempts
- v1.4.0 requires Python ≥ 3.12 and consolidates `.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, and `.llmwiki-pending-prompts/` into a single unified `llmwiki-state.json`
- The `agent`, `agent-delegate`, and `agent_delegate` backends were removed in v1.4.0; misconfigured instances silently fall back to the `dummy` backend and produce stub pages
- `llmwiki add` in v1.4.0+ synthesizes only newly written documents, not the entire backlog as before
- State file access is process-scoped in v1.4.0+, configured once via `--vault`, `--state-file`, or `config.json`

## Key Quotes

> "error: <vault>/llmwiki-state.json: state file was written by a newer llmwiki (schema_version=2 > 1). Upgrade llmwiki, or pass --force-resync to reconvert from scratch"
— The schema versioning guard preventing downgrade-caused silent data loss via reconversion under legacy slug schemes.

> "One-time migration required if your vault still has legacy dotfiles"
— Signals v1.4.0's hard breaking change requiring explicit state file migration.

> "`agent`, `agent-delegate`, and `agent_delegate` were **removed** in v1.4.0. `resolve_backend()` reads them as a typo and silently falls back to `dummy`"
— Silent fallback behavior masks configuration errors in legacy `config.json` files, producing stub pages instead of real synthesis.

## Connections

- [[llmwiki]] (entity) — The system whose upgrade path, versioning strategy, and architectural evolution is documented
  - fact: v1.4.0 consolidated legacy state dotfiles into a unified `llmwiki-state.json`
  - fact: Issue #29 introduced schema versioning guard to prevent data loss from downgrade attempts

- [[Configuration]] (entity) — Configuration schema and backend selection evolved in v1.4.0
  - fact: Backends `agent`, `agent-delegate`, and `agent_delegate` were removed; misconfigured instances silently fall back to `dummy`
  - fact: `vault.default_path` in `config.json` replaces the `LLMWIKI_ROOT` environment variable

- [[Wiki Synthesis]] (concept) — Queue-based and backend architecture underwent hard cutover in v1.4.0
  - fact: New `llmwiki queue` subcommands (`status`, `enqueue`, `run`) replace the SessionStart auto-sync hook
  - fact: `llmwiki add` now synthesizes only newly written documents instead of the entire backlog