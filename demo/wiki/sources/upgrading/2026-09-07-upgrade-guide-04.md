---
title: "Upgrade guide (part 4/5: v1.4.0 — unified queue + vault state (hard cutover))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, v1.4.0-migration, state-consolidation, queue-runner, python-version-requirement]
date: 2026-09-07
source_file: raw/docs/upgrading/upgrade-guide-04.md
project: upgrading
model: 
last_updated: 2026-09-07
---
## Summary

This upgrade documentation source describes v1.4.0 of [[llmwiki]], a major release that consolidates legacy state and queue files into a unified JSON-based state system, bumps the Python requirement to ≥ 3.12, and introduces a new `llmwiki queue` CLI interface. It includes mandatory migration procedures, fixes for queue items corrupted in earlier v1.4.0 snapshots, and removals of unsupported backends.

## Key Claims

- v1.4.0 consolidates four legacy dotfiles/directories (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-pending-prompts/`) into a single vault-rooted `llmwiki-state.json` file with an accompanying `llmwiki-state.js` sidecar
- Python version requirement increases to ≥ 3.12 (from 3.9–3.11), a hard breaking change
- `LLMWIKI_ROOT` environment variable is replaced by `vault.default_path` configuration in `config.json`
- SessionStart auto-sync hook is removed; users must manually invoke `llmwiki queue run` to process tasks
- Synthesis backends `agent`, `agent_delegate`, and `agent-delegate` are removed; only `claude`, `ollama`, and `dummy` are supported going forward
- `llmwiki add` now synthesizes only the documents it just wrote, not the entire backlog
- State file configuration is process-scoped; library code must pass explicit `state_file=` parameter or rely on the centrally configured path

## Key Quotes

> "One-time migration required if your vault still has legacy dotfiles" — establishes that migration is mandatory, not optional

> "`llmwiki` CLI entry points call `configure_state_file` once from `--vault` / `--state-file` / `config.json` `vault.default_path`. Library code and tests must pass an explicit `state_file=` override" — defines the process-scoped state design pattern for v1.4.0+

> "The queue runner has no handler for that type, so `llmwiki queue run` marks every one of them `status: error`" — explains issue #23 where early v1.4.0 migrations leave broken queue items that re-running the migration script will repair

## Connections

- [[llmwiki]] (project) — this is the official upgrade guide for the v1.4.0 release
  - fact: v1.4.0 is a hard cutover requiring a one-time migration
  - fact: Python ≥ 3.12 is now a strict requirement
- [[Configuration]] (concept) — the upgrade involves breaking configuration schema changes
  - fact: `vault.default_path` in `config.json` replaces the `LLMWIKI_ROOT` environment variable
  - fact: Removed `synthesis.backend: agent_delegate` option entirely
- [[Queue System]] (system) — v1.4.0 introduces a unified, centralized queue management system with new CLI commands
  - fact: New commands: `llmwiki queue status`, `llmwiki queue enqueue`, `llmwiki queue run --limit N`
  - fact: Replaces the SessionStart auto-sync hook with explicit manual queue runner invocation