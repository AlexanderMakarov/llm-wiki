---
title: "Refactor the adapter registry so contrib adapters stay opt-in (korvindex)"
type: source
tags: [session, session-transcript, llm-wiki, claude, adapters, auto-discovery, opt-in, registry-refactor, adapter-registry, auto-detection]
date: 2026-06-03
source_file: raw/sessions/llm-wiki/2026-05-11T00-00-llm-wiki-adapter-registry-refactor.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

This session addressed a design flaw in the adapter registry: contrib adapters were being auto-detected alongside core adapters (Claude Code, Codex CLI) without user consent. The solution split the detection logic so core adapters are always probed on every sync, while contrib adapters require explicit opt-in via `--adapter` flag or configuration. A test was added to verify contrib adapters remain silent during default sync runs.

## Key Claims

- The original adapter registry auto-detects all adapters from both `llmwiki/adapters/` (core) and `contrib/` directories indiscriminately.
- Core adapters (Claude Code, Codex CLI) should be probed on every sync without user action.
- Contrib adapters should only load when explicitly named with `--adapter` or enabled in configuration.
- The fix splits the adapter discovery loop based on directory location to enforce different auto-detection policies.
- Contrib adapters will not activate during a default sync even if session data for them already exists.

## Key Quotes

> "The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for." — The problem statement

> "I split the lookup: core adapters are probed on every `sync`, contrib ones only when named with `--adapter` or enabled in config." — The solution approach

## Connections

- [[llmwiki]] (entity) — the CLI framework whose adapter loading mechanism was refactored
- [[Adapters]] (entity) — the pluggable component system being modified to distinguish unconditional (core) from conditional (contrib) discovery
- [[Claude Code]] (entity) — one of two core adapters that auto-detect on every sync
- [[Codex CLI]] (entity) — the other core adapter that auto-detect on every sync
- [[Wiki Synthesis]] (concept) — adapters are the mechanism for ingesting external sources into the wiki, making the registry's loading behavior architecturally significant