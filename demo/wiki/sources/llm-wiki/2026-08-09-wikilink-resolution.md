---
title: "Confirm how cross-references resolve before moving pages"
type: source
tags: [session, session-transcript, llm-wiki, claude, wikilinks, link-resolution, page-structure, page-relocation]
date: 2026-08-09
source_file: raw/sessions/llm-wiki/2026-08-09T23-12-llm-wiki-wikilink-resolution.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session investigated how links resolve in [[WikiLinks]] and determined that they resolve by filename stem, not folder path. This means moving a page to a different folder is safe and doesn't break cross-references, since all link consumers (graph builder, backlink index, reference index, link lint rules) key pages by filename. However, merging pages does break links because the system records aliases but doesn't consult them during resolution.

## Key Claims

- Links resolve by filename stem, not folder path
- All link consumers (graph builder, backlink index, reference index, link lint rules) use filename stem as the key for pages
- Moving a page between folders doesn't break links or affect graph edges, backlinks, or lint results; only the page's URL and kind change
- Merging pages breaks links because aliases are recorded but not consulted during link resolution
- A test was added to verify that moving a page preserves graph edges and backlinks

## Key Quotes

> "Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site."

> "Merging records the old name as an alias, but nothing consults aliases during resolution, so every existing reference to the merged-away name dangles."

## Connections

- [[WikiLinks]] — the cross-reference system whose resolution mechanism was investigated
- [[Knowledge Graph]] — one of the major systems that keys pages by filename stem
- [[Page Relocation]] — how and why pages can be safely moved between folders without breaking references