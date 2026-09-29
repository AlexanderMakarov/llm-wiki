---
title: "Refactor the adapter registry so contrib adapters stay opt-in (korvindex)"
type: source
tags: [session, session-transcript, llm-wiki, claude, adapters, auto-discovery, opt-in, registry-refactor, adapter-registry, auto-detection]
date: 2026-05-31
source_file: raw/sessions/llm-wiki/2026-05-11T00-00-llm-wiki-adapter-registry-refactor.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session refactored the adapter registry to distinguish between core adapters (Claude Code, Codex CLI) and contrib adapters. Core adapters now auto-detect on every sync, while contrib adapters require explicit enablement via `--adapter` flag or config. The implementation separates detection logic based on directory location and includes test coverage to verify contrib adapters remain silent on default sync.

## Key Claims

- The original adapter registry auto-detected all adapters indiscriminately, including contrib adapters users never requested
- Core adapters live in `llmwiki/adapters/` while contrib adapters are in `contrib/`
- The original detection loop treated both directory structures identically, causing unwanted auto-detection of contrib adapters
- The refactored solution probes core adapters on every sync while contrib adapters only activate when named with `--adapter` or enabled in config
- A test was added to ensure contrib adapters remain silent during default sync even when session stores exist

## Key Quotes

> "The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for." — Identifies the core problem: unintended auto-discovery of optional adapters

> "I split the lookup: core adapters are probed on every `sync`, contrib ones only when named with `--adapter` or enabled in config." — Describes the solution: differentiated detection behavior

## Connections

- [[Adapters]] (entity) — The registry and loading system being refactored to distinguish core from contrib
  - fact: Core adapters (Claude Code, Codex CLI) in `llmwiki/adapters/` now auto-detect on every sync
  - fact: Contrib adapters in `contrib/` require explicit `--adapter` flag or config enablement

- [[Claude Code]] (entity) — One of the core adapters with automatic detection behavior
  - fact: Classified as a core adapter and remains auto-detected without user configuration

- [[Codex CLI]] (entity) — The other core adapter with automatic detection behavior
  - fact: Classified as a core adapter and remains auto-detected without user configuration

- [[Configuration]] (entity) — Mechanism for enabling optional contrib adapters
  - fact: Contrib adapters can be explicitly enabled through configuration files or command-line flags

- [[llmwiki]] (entity) — The knowledge base system improved by this refactoring
  - fact: The adapter registry is a core component enabling session ingestion from multiple sources

## Contradictions

None identified. This session documents a new feature that refines the adapter registry without contradicting existing documented behavior.