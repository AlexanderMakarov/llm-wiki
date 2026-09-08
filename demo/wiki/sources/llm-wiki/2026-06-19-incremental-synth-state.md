---
title: "Stop re-synthesising sources that have not changed"
type: source
tags: [session, session-transcript, llm-wiki, claude, incremental-synthesis, state-comparison, filesystem-mtimes, fresh-clone]
date: 2026-06-19
source_file: raw/sessions/llm-wiki/2026-06-19T20-09-llm-wiki-incremental-synth-state.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session traced why running `synth` twice reprocessed all sources instead of being a no-op. The bug was in the state file's modification time comparison—it used strict greater-than (>) instead of greater-or-equal (>=)—causing files with exact timestamp matches to look new. The fix added a small epsilon for filesystem timestamp resolution, making repeated runs properly skip unchanged sources. However, the fix doesn't survive fresh clones, where git checkout rewrites modification times, revealing a deeper architectural need for content hashing.

## Key Claims

- The state file comparison used strict `>` instead of `>=` for modification times, causing exact timestamp matches to appear new
- A small epsilon tolerance was added to handle filesystem timestamp resolution differences
- After the fix, running synth twice correctly skips all sources (no-op behavior)
- Fresh clones rewrite file modification times via checkout, causing all sources to appear new on the next synth run
- Content hashing would be a more robust long-term solution but requires state file migration

## Key Quotes

> "The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new." — Root cause of the reprocessing bug

> "Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus." — Reveals the limitation of the mtime-based approach

## Connections

- [[Wiki Synthesis]] (concept) — the incremental synthesis mechanism that should avoid reprocessing unchanged sources; the state comparison logic is core to this behavior
- [[llmwiki]] (entity) — the project where state tracking and comparison happens during synthesis