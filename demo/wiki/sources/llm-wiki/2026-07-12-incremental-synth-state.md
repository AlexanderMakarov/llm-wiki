---
title: "Stop re-synthesising sources that have not changed"
type: source
tags: [session, session-transcript, llm-wiki, claude, incremental-synthesis, state-comparison, filesystem-mtimes, fresh-clone, state-tracking, file-mtime, timestamp-comparison]
date: 2026-07-12
source_file: raw/sessions/llm-wiki/2026-06-19T20-09-llm-wiki-incremental-synth-state.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Fixed a critical bug in incremental source synthesis where modification time comparison used strictly greater-than instead of greater-or-equal, causing sources to be incorrectly re-synthesized on every run. Added epsilon tolerance for filesystem timestamp precision. Second runs now correctly skip all unchanged sources. The session also identified a limitation: fresh clones reprocess all sources due to git checkout rewriting modification times, which would require content-hash–based state tracking to solve properly (deferred to issue tracker).

## Key Claims

- The state file records modification time per source to detect which sources need re-synthesis
- The original comparison used `>` (strictly greater-than) instead of `>=`, causing files with exactly matching timestamps to be incorrectly treated as new
- Adding epsilon tolerance prevents false positives on filesystems with coarse timestamp granularity
- A second synth run on the same clone now reports all sources as `skipped`
- Fresh clones reprocess all sources because `git checkout` rewrites file modification times
- Content-hash–based state tracking would solve the fresh-clone limitation but requires state file migration

## Key Quotes

> "The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new." — identifying the root cause

> "A second run is now genuinely a no-op — the run summary reports `skipped` for every source." — demonstrating the fix works on same clone

> "Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus." — identifying the limitation with fresh clones

## Connections

- [[llmwiki]] (entity) — the CLI synthesis tool where state comparison logic was fixed
  - fact: Modified llmwiki/llm_wiki/handler.py to fix timestamp comparison operator and add epsilon tolerance
- [[Wiki Synthesis]] (concept) — source synthesis process that is optimized by incremental state tracking
  - fact: Incremental synthesis prevents re-processing sources whose modification time has not changed
- [[Incremental Synthesis]] (concept) — strategy of tracking source state to skip re-synthesis of unchanged sources
  - fact: Relies on comparing source modification times; epsilon tolerance handles filesystem timestamp precision issues