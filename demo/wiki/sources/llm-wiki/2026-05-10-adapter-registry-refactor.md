---
title: "Refactor the adapter registry so contrib adapters stay opt-in"
type: source
tags: [session, session-transcript, llm-wiki, claude, adapter-registry, opt-in-adapters, auto-detection]
date: 2026-05-10
source_file: raw/sessions/llm-wiki/2026-05-10T00-00-llm-wiki-adapter-registry-refactor.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session refactored the adapter registry to distinguish between core and contributed adapters. Core adapters ([[Claude Code]] and [[Codex CLI]] in `llmwiki/adapters/`) now auto-detect on every sync, while contrib adapters (in `contrib/`) require explicit opt-in via `--adapter` flag or config. The `llmwiki adapters` listing command remains unchanged so users can still discover all available adapters; contrib rows now display an opt-in marker to indicate their optional nature.

## Key Claims

- The adapter registry previously auto-detected all adapters regardless of origin, causing unsolicited contrib adapter activation.
- Core adapters ([[Claude Code]] and [[Codex CLI]]) are located in `llmwiki/adapters/` and auto-probe on every sync.
- Contributed adapters are in `contrib/` and only activate when explicitly named via `--adapter` flag or enabled in config.
- The `llmwiki adapters` listing command shows all available adapters with status, including an opt-in marker for contrib entries, preserving discoverability.
- Test coverage verifies that contrib adapters remain inactive on default sync even when their session store exists.

## Key Quotes

> "The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for. Can we make core auto-detect and contrib opt-in?"
— Identifies the problem: users receiving unwanted adapters without explicit request.

> "I split the lookup: core adapters are probed on every `sync`, contrib ones only when named with `--adapter` or enabled in config."
— Core solution via separate detection paths for different adapter tiers.

> "`llmwiki adapters --wide` shows every adapter with a present/absent column, and contrib rows now carry an `opt-in` marker so the distinction is visible before you run a sync."
— Ensures contrib adapters remain discoverable while clearly signaling their optional activation.

## Connections

- [[Adapters]] (system) — The plugin architecture was refactored to support layered activation: core auto-detect vs contrib opt-in.
  - fact: The adapter registry detection loop split into separate probes for core and contrib directories.
  - fact: Contrib adapters now require explicit request to activate, preventing accidental addon loading.

- [[Claude Code]] (adapter) — Core adapter that auto-detects on every sync under the new registry design.
  - fact: Located in `llmwiki/adapters/` (not `contrib/`), ensuring default activation.

- [[Codex CLI]] (adapter) — Core adapter that auto-detects alongside [[Claude Code]].
  - fact: Located in `llmwiki/adapters/`, designated as core rather than contributed.

- [[llmwiki]] (project) — The main project receiving adapter registry refactoring on branch `feat/adapters`.
  - fact: CLI command `llmwiki adapters` updated to display opt-in status for contrib rows.