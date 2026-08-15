---
title: "Split the search index into per-project chunks"
type: source
tags: [session, session-transcript, llm-wiki, claude, search-index, lazy-loading, performance, static-site]
date: 2026-08-07
source_file: raw/sessions/llm-wiki/2026-08-07T19-20-llm-wiki-search-index-chunks.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session addressed a performance bottleneck where the wiki's search feature was slow on large vaults due to downloading a monolithic index file before any search interaction could occur. The solution split the index into per-project chunks with a small manifest loaded upfront and individual chunks fetched on-demand. This eliminates the initial pause on large vaults while maintaining compatibility with file-opened pages by emitting chunks as script files rather than JSON.

## Key Claims

- The original search index was a single file that had to be completely downloaded before search functionality became available
- Splitting the index into per-project chunks with lazy loading eliminates the initial latency on large vaults
- Chunks are stored as script files rather than JSON to preserve search functionality for pages opened directly from the filesystem

## Key Quotes

> "The whole index was one file, downloaded before the first keystroke." — Explains the performance bottleneck of the original monolithic index design.

> "On a vault with a thousand sessions it is the difference between a pause and none." — Quantifies the performance impact: negligible on small datasets, but a significant improvement on large vaults.

> "The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches." — Explains why scripts are used instead of JSON: to maintain search functionality for offline/file-opened pages.

## Connections

- [[Static Site]] — The wiki's static site deployment model necessitates that search work without server-side logic; script-based chunks enable this in both HTTP and file-opened contexts
- [[Search]] — Core feature being optimized; the chunking strategy reduces initial latency by deferring index loads until needed

## Contradictions

None identified.