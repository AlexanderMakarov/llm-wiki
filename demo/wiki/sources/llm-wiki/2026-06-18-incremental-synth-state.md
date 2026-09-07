---
title: "Stop re-synthesising sources that have not changed"
type: source
tags: [session, session-transcript, llm-wiki, claude, incremental-synthesis, state-tracking, mtime-comparison, git-checkout-timestamps]
date: 2026-06-18
source_file: raw/sessions/llm-wiki/2026-06-18T20-09-llm-wiki-incremental-synth-state.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Investigated why running `synth` twice re-processed all sources instead of skipping unchanged ones. Found that the state file's modification-time comparison was using strict `>` instead of `>=`, causing files with identical recorded and actual timestamps to appear new. Fixed the comparison and added epsilon for filesystem timestamp resolution coarseness. Discovered the fix does not survive a fresh clone, since git checkout rewrites modification times; content hashing with state-file migration would be the proper long-term solution.

## Key Claims

- State file comparison used `>` instead of `>=` for modification times, causing false positives on unchanged files
- Epsilon was added to handle coarse filesystem timestamp resolution (preventing flips on boundary conditions)
- Second `synth` runs are now a no-op when sources haven't changed (reported as `skipped`)
- Fresh clones re-process the entire corpus because git checkout rewrites all file modification times
- Content hashing would be the proper solution but requires state file migration

## Key Quotes

> "The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new."

> "Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus."

## Connections

- [[Wiki Synthesis]] (topic) — optimizing the incremental synthesis process to avoid redundant work
  - fact: Idempotent synthesis runs require correct state comparison logic and account for filesystem timestamp limitations.
- [[llmwiki]] (project) — the main system whose performance was improved

## Notes

None with existing documented wiki content, but the limitation that fresh clones trigger full re-processing (vs. the fix's assumption of a stable state file) is worth recording as a known edge case for future state-migration work.