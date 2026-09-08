---
title: "Split the search index into per-project chunks"
type: source
tags: [session, session-transcript, llm-wiki, claude, search-index, lazy-loading, frontend-performance]
date: 2026-09-05
source_file: raw/sessions/llm-wiki/2026-09-05T19-20-llm-wiki-search-index-chunks.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session covered a refactoring of the static site's search index from a single monolithic file to per-project chunks with lazy loading. The original design blocked interactivity while downloading the full index; the new implementation loads a small manifest first, then fetches individual project chunks on-demand. Critically, chunks are emitted as script files rather than JSON to preserve search functionality when the page is opened offline (via `file://` protocol).

## Key Claims

- The original search implementation downloaded an entire index file before search became usable
- The refactored index splits per-project with a small manifest loaded up front
- Individual index chunks are fetched on-demand when results from a project are needed
- Index chunks are emitted as script files (not JSON) to support offline/file:// access
- On a vault with ~1,000 sessions, this eliminates the perceived pause during initial page load

## Key Quotes

> "The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed." — Describes the core optimization.

> "The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches." — Explains why script files were chosen over fetched JSON: to preserve offline functionality.

## Connections

- [[llmwiki]] (project) — the static wiki generator where search is a frontend feature
  - fact: Search index refactored from monolithic to chunked per-project layout to improve load-time performance
- [[Static Site]] (system) — the deployed output where frontend search runs
  - fact: Frontend optimization removes perceptible delay on large vaults by deferring chunk downloads
