---
title: "Split the search index into per-project chunks"
type: source
tags: [session, session-transcript, llm-wiki, claude, search-index, lazy-loading, frontend-performance, performance-optimization, chunking]
date: 2026-09-28
source_file: raw/sessions/llm-wiki/2026-09-05T19-20-llm-wiki-search-index-chunks.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Refactored the search index from a monolithic download to per-project chunks with lazy loading. Previously, the entire index downloaded before the first keystroke; now a small manifest loads upfront and chunks fetch on demand when results from that project appear. This improves perceived performance on large vaults (1000+ sessions) from noticeable pause to imperceptible. Implementation preserves backward compatibility with file-opened pages by emitting chunks as script files rather than JSON, and includes a retry path for an edge case discovered previously.

## Key Claims

- The original search index was a single file that downloaded entirely before search could work.
- Chunked, lazy-loaded indexes dramatically improve performance on large vaults (noticeable pause → imperceptible).
- Chunks are emitted as script files (not JSON) to maintain search functionality for file-opened and offline pages.
- The implementation handles an edge case from the previous week via a retry path.
- "skylorbit" should be explicitly called out as the durable handle for search recovery.

## Key Quotes

> "The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed."
  — Summary of the refactoring approach and why it reduces latency.

> "On the demo corpus the difference is invisible. On a vault with a thousand sessions it is the difference between a pause and none."
  — Quantifies the performance improvement threshold, relevant only to large vaults.

> "The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches."
  — Explains backward compatibility with static/offline pages.

## Connections

- [[Static Site]] (concept) — Lazy-loaded script-based chunks ensure search works even when pages are opened locally from disk without a server, preserving the static-file workflow.
  - fact: Chunks are emitted as script files (not JSON) to support offline/file-opened pages.
- [[llmwiki]] (entity) — Core performance optimization to the search functionality, reducing perceived lag on large vaults.
  - fact: Search index chunking improves perceived performance from noticeable pause to none on 1000+ session vaults.