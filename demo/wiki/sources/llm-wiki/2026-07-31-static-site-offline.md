---
title: "Make the built site work without a server or a network"
type: source
tags: [session, session-transcript, llm-wiki, claude, offline-first, vendoring, knowledge-graph, data-embedding]
date: 2026-07-31
source_file: raw/sessions/llm-wiki/2026-07-31T20-45-llm-wiki-static-site-offline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session enabled the llm-wiki site to run completely offline by eliminating two architectural blockers. The knowledge graph visualization library, previously loaded from a CDN, was vendored locally with a pinned version and license documentation. Page data, previously fetched as JSON (which fails when opening HTML from disk due to browser same-origin restrictions), is now embedded as a script tag in the HTML itself. This dual change allows the same static file to work identically over HTTP and when opened directly from disk. Only the candidates page still requires server infrastructure for posting review decisions.

## Key Claims

- The graph library was previously loaded from a CDN, causing it to be unavailable on offline machines; it is now vendored beside the page with a pinned version and license notice
- Page data was previously fetched as JSON, but browsers block file-opened pages from fetching sibling files; moving data to an embedded script tag removes this constraint
- Embedding data in a script tag enables identical loading behavior over HTTP and from the file protocol
- The site is now entirely static except for the candidates page, which still requires a server endpoint for posting review decisions

## Key Quotes

> "The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence."
— Identifies and solves the first offline blocker

> "The bigger one: page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk."
— The core architectural shift enabling offline-first deployment

> "Only the candidates page, which posts review decisions to a small endpoint. Everything else — home, projects, sessions, topics, search, graph — is static."
— Clarifies remaining server dependencies

## Connections

- [[Knowledge Graph]] — the graph visualization library was vendored to enable offline access
- [[Static Site]] — the deployment model shifted entirely to static generation with embedded data
- [[Deployment]] — eliminates the requirement for a running server in most scenarios