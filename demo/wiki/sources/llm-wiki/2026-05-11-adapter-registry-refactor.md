---
title: "Refactor the adapter registry so contrib adapters stay opt-in"
type: source
tags: [session, session-transcript, llm-wiki, claude, adapters, auto-discovery, opt-in, registry-refactor]
date: 2026-05-11
source_file: raw/sessions/llm-wiki/2026-05-11T00-00-llm-wiki-adapter-registry-refactor.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session refactored the adapter auto-detection system to split core adapters (Claude Code, Codex CLI) from optional contrib adapters. Core adapters now auto-detect on every sync, while contrib adapters require explicit enablement via `--adapter` flag or config. The `llmwiki adapters` listing remains comprehensive but adds an `opt-in` marker to distinguish contrib adapters, maintaining discoverability while preventing unwanted activation.

## Key Claims

- The adapter registry was previously treating core and contrib adapters identically, auto-detecting all of them without explicit user consent.
- Core adapters (Claude Code and Codex CLI) are now probed on every sync, while contrib adapters only activate when explicitly named or enabled in configuration.
- The `llmwiki adapters` command still lists all available adapters (both core and contrib) for discovery, separating the listing interface from the activation mechanism.
- Contrib adapters will not activate on a default sync even if their session store exists, unless explicitly enabled.
- The contrib adapter distinction is now visually marked in the listing output with an `opt-in` label.

## Key Quotes

> "The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for. Can we make core auto-detect and contrib opt-in?" — User request capturing the design problem.

> "Split the lookup: core adapters are probed on every sync, contrib ones only when named with `--adapter` or enabled in config." — Core solution implemented.

> "listing is separate from activation" — Design principle clarifying that discoverability remains independent of enablement.

## Connections

- [[Adapters]] (system) — the registry being refactored to support staged auto-detection; core adapters auto-probe while contrib require explicit opt-in.
- [[llmwiki]] (project) — the CLI application and vault ecosystem modified by this refactor.
- [[Configuration Reference]] (documentation) — how users explicitly enable contrib adapters via flags and config files.
- [[Codex CLI]] (adapter) — one of the two core adapters that auto-detects.
- [[Claude Code]] (adapter) — one of the two core adapters that auto-detects.
