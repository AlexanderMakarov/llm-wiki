---
title: "Split the search index into per-project chunks"
type: source
tags: [session, session-transcript, llm-wiki, claude, search-index, lazy-loading, frontend-performance, performance-optimization]
date: 2026-09-25
source_file: raw/sessions/llm-wiki/2026-09-05T19-20-llm-wiki-search-index-chunks.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Refactored the llmwiki search index from eager downloading of a single monolithic file to lazy-loaded per-project chunks. A small manifest is downloaded upfront, with individual chunks fetched only when their results appear in search. Implementation uses script files rather than JSON to preserve offline search capability on locally opened pages, and includes a retry path for an edge case discovered previously.

## Key Claims

- The search index is now split into per-project chunks with lazy loading instead of downloading the entire index upfront
- On a large vault with 1000+ sessions, performance improves from a noticeable pause to imperceptible
- Chunks are emitted as script files rather than JSON, preserving offline search capability for pages opened locally without network access
- A retry path addresses an edge case discovered in previous development iterations
- The implementation is ready to ship after code linting and passing the focused test suite, with the full test suite deferred to CI

## Key Quotes

> "The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed."
— Explains the architectural shift from eager to lazy loading.

> "On a vault with a thousand sessions it is the difference between a pause and none."
— Quantifies the performance improvement on realistic large-scale vaults.

> "The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches."
— Justifies the design choice to maintain offline search capability.

## Connections

- [[llmwiki]] (entity) — the wiki system whose search startup performance was optimized through index chunking
  - fact: Search index now splits per-project with lazy loading, eliminating startup delay on large vaults.
- [[Static Site]] (entity) — the static HTML frontend that must support both networked and offline search access
  - fact: Index chunks are emitted as script files to enable search functionality when pages are opened from disk.