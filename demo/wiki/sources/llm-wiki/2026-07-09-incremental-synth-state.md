---
title: "Stop re-synthesising sources that have not changed"
type: source
tags: [session, session-transcript, llm-wiki, claude, incremental-synthesis, state-comparison, filesystem-mtimes, fresh-clone, state-tracking, file-mtime]
date: 2026-07-09
source_file: raw/sessions/llm-wiki/2026-06-19T20-09-llm-wiki-incremental-synth-state.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session traced why repeated `synth` runs re-processed all sources instead of skipping unchanged ones. The root cause was a strict greater-than comparison in the state file logic: files with modification times exactly matching their recorded state were incorrectly flagged as new. Fixing the comparison to `>=` and adding epsilon tolerance for coarse filesystem timestamps resolved the issue for same-filesystem re-runs. A fresh clone edge case was identified—git checkout resets all modification times, causing full re-synthesis—but was deferred in favor of a longer-term content hashing solution that would require state file migration.

## Key Claims

- The state file comparison used `>` instead of `>=` when checking modification times, causing exact timestamp matches to be treated as new sources
- Epsilon tolerance was added to handle filesystem timestamp resolution variance
- After the fix, a second synth run on the same filesystem correctly skips all sources
- Git checkout rewrites file modification times, so fresh clones incorrectly re-synthesize the entire corpus on the next run
- Content hashing would solve the fresh clone problem properly but requires state file format migration

## Key Quotes

> "The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new." — Root cause of the re-synthesis bug

> "A second run is now genuinely a no-op — the run summary reports `skipped` for every source." — Confirmation the fix works for repeated runs

> "Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus. Content hashing would fix it properly; the state file would need a migration." — Long-term perspective on remaining edge cases

## Connections

- [[Wiki Synthesis]] (entity) — the incremental processing pipeline whose efficiency is optimized by state tracking
  - fact: Detecting unchanged sources via modification time or content hash enables skip-based incremental synthesis rather than re-processing the entire corpus.