---
title: "Refactor the adapter registry so contrib adapters stay opt-in"
type: source
tags: [session, session-transcript, llm-wiki, claude, adapter-registry, opt-in-pattern, auto-detection, cli-discovery]
date: 2026-04-12
source_file: raw/sessions/llm-wiki/2026-04-12T00-00-llm-wiki-adapter-registry-refactor.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

Refactored the [[Adapter Registry]] to distinguish core from contrib adapters: core ones ([[Claude Code]], [[Codex CLI]]) now auto-detect on every sync, while contrib adapters require explicit activation via `--adapter` flag or config. The `llmwiki adapters` listing command remains unchanged to preserve discoverability, but now marks contrib entries with an `opt-in` label to clarify the distinction.

## Key Claims

- The original registry detection loop treated core and contrib adapters identically, causing unwanted auto-activation of contrib adapters.
- Core adapters live in `llmwiki/adapters/`, contrib adapters in `contrib/`, and the refactor splits the lookup logic to probe them separately.
- A test was added to verify contrib adapters remain inactive during a default sync even if their session store exists.
- Listing and activation are architecturally separate: `llmwiki adapters --wide` shows all available adapters with a present/absent column and opt-in markers, but does not activate them.

## Key Quotes

> "The detection loop treats both directories identically, which is the bug." — identified the root cause

> "Listing is separate from activation." — design principle for the CLI interface

> "Contrib rows now carry an `opt-in` marker so the distinction is visible before you run a sync." — UX solution for discovery

## Connections

- [[Adapter Registry]] — the core system being refactored to support opt-in vs. auto-detect modes
- [[Claude Code]] — one of the two core adapters that auto-detect
- [[Codex CLI]] — the other core adapter that auto-detect