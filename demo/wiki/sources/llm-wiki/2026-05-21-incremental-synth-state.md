---
title: "Stop re-synthesising sources that have not changed"
type: source
tags: [session, session-transcript, llm-wiki, claude, incremental-synthesis, mtime-comparison, state-management]
date: 2026-05-21
source_file: raw/sessions/llm-wiki/2026-05-21T20-09-llm-wiki-incremental-synth-state.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

A critical bug in the [[Wiki Synthesis]] pipeline caused subsequent runs to re-process all sources even when nothing had changed. The root cause was a state comparison using strict `>` instead of `>=`, combined with filesystem timestamp precision issues. The fix adds an epsilon to the comparison, making a second run genuinely a no-op. However, fresh clones still trigger full re-processing because git checkout rewrites modification times; content hashing was identified as a proper long-term solution but deferred.

## Key Claims

- The state file stores per-source modification times for incremental processing, but comparison logic used `>` instead of `>=`
- A file whose timestamp exactly matched its recorded state value was incorrectly flagged as new
- Adding an epsilon to timestamp comparison tolerates filesystems with coarse timestamp resolution
- After the fix, a second synth run correctly skips all sources that haven't changed (confirmed by run summary reporting `skipped` for every source)
- Fresh clones still cause full re-processing because git checkout rewrites file modification times, making every source appear new
- Content hashing would solve the fresh clone problem but requires state file migration

## Key Quotes

> "The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new."

— Identifies the precise off-by-one error in the comparison logic

> "Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus."

— Explains a separate but related limitation of the timestamp-based approach

> "Content hashing would fix it properly; the state file would need a migration. I have written it up rather than changing it here."

— Notes the architectural solution and rationale for deferring it

## Connections

- [[Wiki Synthesis]] — the session debugs and improves core synthesis pipeline efficiency
- [[Incremental Sync]] — this session enables proper incremental processing by fixing state comparison