---
title: "Confirm how cross-references resolve before moving pages"
type: source
tags: [session, session-transcript, llm-wiki, claude, wikilinks, link-resolution, page-relocation, merge-behavior, filename-resolution, graph-consistency]
date: 2026-09-27
source_file: raw/sessions/llm-wiki/2026-09-07T23-12-llm-wiki-wikilink-resolution.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

This session confirmed a critical design principle: in llmwiki, link resolution is based on filename (file stem), not folder path. This means pages can be safely moved between folders without breaking cross-references, provided the filename remains unchanged. The assistant added a test verifying that graph edges, backlinks, and lint results remain consistent after page relocation.

## Key Claims

1. All wiki consumers—graph builder, backlink index, reference index, and lint rules—key pages by filename rather than folder path.
2. A page's folder determines only its content kind and resulting URL on the static site; it does not affect link resolution.
3. Pages can be relocated between folders without breaking incoming or outgoing links, provided the filename stays the same.
4. A test was added that relocates a page and asserts that graph edges, backlinks, and lint results remain unchanged.

## Key Quotes

> "Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site." — Explains the architecture of link resolution

> "So moving a page between folders is safe as long as the filename is unchanged." — Core principle enabling page relocation

## Connections

- [[Wikilinks]] (entity) — the cross-reference mechanism that resolves by file stem
- [[Knowledge Graph]] (entity) — the interconnected structure that remains consistent during page moves
- [[Lint Rules]] (concept) — one of the components that keys pages by filename