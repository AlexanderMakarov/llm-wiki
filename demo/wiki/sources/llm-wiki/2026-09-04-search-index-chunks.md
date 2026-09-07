---
title: "Split the search index into per-project chunks"
type: source
tags: [session, session-transcript, llm-wiki, claude, search-index, lazy-loading, offline-first, static-site]
date: 2026-09-04
source_file: raw/sessions/llm-wiki/2026-09-04T19-20-llm-wiki-search-index-chunks.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session optimized search performance on large knowledge bases by replacing a monolithic index file with a chunked, lazy-loading architecture. The new system loads a small manifest on page load and fetches individual per-project index chunks only when results from that project are needed. To preserve offline (file://) access, chunks are emitted as inline script files rather than fetched JSON, eliminating the need for XHR requests.

## Key Claims

- The original search index was a single file downloaded entirely before the user's first search keystroke
- On vaults with ~1000 sessions, the chunked approach eliminates a noticeable pause that existed with the monolithic index  
- Chunks are emitted as inline script files to support file:// protocol access for pages opened locally from disk

## Key Quotes

> "The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed." — Describes the shift from eager to on-demand loading

> "The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches." — Demonstrates how offline functionality is preserved despite lazy-loading architecture

## Connections

- [[Static Site]] (system) — the compiled wiki output where search runs; now uses per-project index chunks loaded on demand rather than downloaded upfront

## Contradictions

None noted.