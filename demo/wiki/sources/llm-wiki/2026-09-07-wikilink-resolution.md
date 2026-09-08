---
title: "Confirm how cross-references resolve before moving pages"
type: source
tags: [session, session-transcript, llm-wiki, claude, wikilinks, link-resolution, page-relocation, merge-behavior]
date: 2026-09-07
source_file: raw/sessions/llm-wiki/2026-09-07T23-12-llm-wiki-wikilink-resolution.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session established that wikilink resolution in llmwiki is based on filename stem rather than folder path. Moving a page between folders is therefore safe as long as the filename remains unchanged. However, the session identified a limitation: when pages are merged, the old name becomes an alias, but aliases are never consulted during link resolution, causing references to merged-away pages to become dangling links.

## Key Claims

- All link consumers (graph builder, backlink index, reference index, lint rules) resolve by filename stem, not folder path
- Folder placement only affects page kind and generated URL, not how links resolve to a page  
- Relocating a page between folders is safe as long as the filename is unchanged; this is verified by automated tests that assert graph edges, backlinks, and lint results remain identical
- When a page is merged, the old name is recorded as an alias but is never consulted during resolution, leaving all references to the merged name as dangling links

## Key Quotes

> "Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site."

This design decision ensures page relocation is safe and explains why folder reorganization doesn't break links.

> "Merging records the old name as an alias, but nothing consults aliases during resolution, so every existing reference to the merged-away name dangles."

This reveals a gap in the alias system where page consolidation breaks existing references.

## Connections

- [[Wikilinks]] (system) — the double-bracket link syntax and resolution mechanism  
  - fact: Wikilinks resolve by filename stem, enabling safe page relocation between folders without breaking references.
  - fact: Aliases created during page merges are not consulted during link resolution, causing merge scenarios to create dangling links.

- [[Knowledge Graph]] (system) — explicitly identified as one of the key consumers of filename-based resolution
  - fact: The graph builder's reliance on filename-based resolution ensures semantic edges remain valid after page relocation.