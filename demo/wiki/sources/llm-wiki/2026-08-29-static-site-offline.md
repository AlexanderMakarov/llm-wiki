---
title: "Make the built site work without a server or a network"
type: source
tags: [session, session-transcript, llm-wiki, claude, offline-first, cdn-vendoring, script-tag-state]
date: 2026-08-29
source_file: raw/sessions/llm-wiki/2026-08-29T20-45-llm-wiki-static-site-offline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session addressed making llmwiki's built static site work offline by vendoring the graph visualization library (previously loaded from a CDN) and moving page state from JSON fetches to embedded script tags, which work from file:// URLs. Only the candidates page still requires a server for review endpoints.

## Key Claims

- The graph library was previously loaded from a CDN, making it unavailable offline
- Page data was fetched as JSON, which cannot work when opening HTML files directly from disk (file:// protocol restriction)
- Page state is now embedded in script tags, allowing the same code to work both offline and over HTTP
- All site features except the candidates page are now fully static and require no server

## Key Quotes

> "The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence." — explains the rationale for vendoring

> "page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk." — describes the key technical solution

## Connections

- [[llmwiki]] (project) — the static site project now supporting offline file-based browsing
  - fact: Vendored the graph library with pinned version and license notice for offline use
- [[Static Site]] (topic) — static HTML output works from file:// URLs without a server
  - fact: All features work offline except candidates page, which requires server-side review endpoints
- [[Knowledge Graph]] (topic) — the graph visualization library was the primary offline blocker
  - fact: Graph library moved from CDN to local vendor directory for offline availability
