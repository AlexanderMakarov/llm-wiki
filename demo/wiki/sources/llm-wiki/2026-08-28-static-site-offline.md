---
title: "Make the built site work without a server or a network"
type: source
tags: [session, session-transcript, llm-wiki, claude, offline-first, vendoring, cors-fetch, graph-library]
date: 2026-08-28
source_file: raw/sessions/llm-wiki/2026-08-28T20-45-llm-wiki-static-site-offline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

This session made the built llmwiki site fully usable offline by addressing two infrastructure dependencies. The graph visualization library was vendored locally instead of loading from a CDN, and page data was moved from JSON fetches to inline script tags to work around file:// protocol limitations. The candidates page remains the only component requiring server infrastructure for the review decision endpoint.

## Key Claims

- The graph library was vendored with a pinned version and license notice to eliminate the CDN dependency
- Page data is now emitted as inline script tags in HTML, enabling identical behavior over HTTP and from file:// URLs  
- File protocol cannot fetch sibling files but can execute inline scripts, making script tags a suitable fetch replacement
- The candidates page is the only remaining component requiring a server for posting review decisions

## Key Quotes

> "The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence."
- Explains the CDN-to-vendoring shift and why an offline viewer is now available

> "page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk."
- The key technical insight: why inline scripts bypass file:// fetch limitations while maintaining identical code paths

## Connections

- [[Static Site]] (concept) — the session made the compiled output fully offline-capable
  - fact: Vendored graph library and inlined page data eliminated external dependencies that previously prevented file:// access
- [[Knowledge Graph]] (concept) — the graph visualization library became a vendored local dependency
  - fact: Graph library moved from CDN link to a vendored directory with version pinning and license attribution