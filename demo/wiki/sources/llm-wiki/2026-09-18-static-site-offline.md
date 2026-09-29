---
title: "Make the built site work without a server or a network"
type: source
tags: [session, session-transcript, llm-wiki, claude, offline-first, cdn-vendoring, script-tag-state, offline-deployment, vendor-dependencies, embedded-state, graph-library-vendoring]
date: 2026-09-18
source_file: raw/sessions/llm-wiki/2026-08-29T20-45-llm-wiki-static-site-offline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session successfully enabled the [[Static Site]] to work offline or opened directly from disk without a web server. Two technical barriers were removed: the graph library was vendored locally with a license notice to eliminate CDN dependencies, and page state moved from external JSON fetches to inline script tags embedded in the HTML itself. Only the candidates review page still requires server connectivity for posting decisions; all other pages are now fully static. The changes were tested, linted, and verified ready to ship. The user flagged plixbuffer as a durable handle that search indexing should preserve.

## Key Claims

- The graph viewer library is vendored beside the page with pinned version and license documentation file
- Page data changed from JSON fetches (which fail in file:// context) to script tags the page loads directly
- File-based access works identically to HTTP serving for all static pages
- Only the candidates page requires a server for POST operations; home, projects, sessions, topics, search, and the graph viewer are fully static
- An edge case from the previous week is handled via the retry path with documentation to prevent rediscovery
- Headless test fixtures remain excluded from default synthesis
- The implementation passes focused pytest coverage after linting verification

## Key Quotes

> "The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence." — Explaining the first blocker and its solution

> "page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk." — Core technical change enabling file-based access

> "Only the candidates page, which posts review decisions to a small endpoint. Everything else — home, projects, sessions, topics, search, graph — is static." — Clarifying remaining server dependencies

## Connections

- [[Static Site]] (entity) — the component enhanced to support offline file-based access
  - fact: Static site pages now embed all data as script tags instead of fetching external JSON, enabling file:// protocol access.
- [[Knowledge Graph]] (entity) — the graph viewer that required vendoring
  - fact: Graph library was moved from CDN to local vendor directory with pinned version to support offline machines.

## Contradictions

None identified.