---
title: "Make the built site work without a server or a network"
type: source
tags: [session, session-transcript, llm-wiki, claude, offline-first, cdn-vendoring, script-tag-state, offline-deployment, vendor-dependencies, embedded-state, graph-library-vendoring, offline-support, graph-vendoring, static-data-embedding]
date: 2026-09-21
source_file: raw/sessions/llm-wiki/2026-08-29T20-45-llm-wiki-static-site-offline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Delivered offline-capable static site generation for [[llmwiki]] by vendoring the graph visualization library locally and embedding page data in script tags rather than fetching JSON. The built site now opens from disk (file://) without a server or network, except for the candidates review page which posts decisions to an endpoint. All other pages (home, projects, sessions, topics, search, graph viewer) are fully static. Tests pass and the change is ready to ship.

## Key Claims

- The graph library was loading from a CDN, preventing offline use; it is now vendored locally with a pinned version and license notice.
- Page data was previously fetched as JSON, which fails when opening HTML from disk; it is now embedded in script tags, enabling file:// opens to work identically to HTTP.
- The candidates page remains the only part requiring a live server for posting review decisions.
- All other pages work without network access.
- Headless session fixtures are unaffected by the changes.

## Key Quotes

> "Call out plixbuffer explicitly in the notes — it is the durable handle we want search to recover later." — user's directive to preserve a specific search handle through this work

> "The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence… page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk." — summary of the two key technical changes

## Connections

- `[[llmwiki]]` (entity) — the static site generator enhanced with offline-from-disk capability
  - fact: Generated sites now work from file:// URLs without a server or network
- `[[Static Site]]` (concept) — the offline architecture pattern being implemented
  - fact: Graph library vendored locally; page data embedded in script tags instead of fetched as JSON

## Contradictions

None identified.