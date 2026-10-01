---
title: "Confirm how cross-references resolve before moving pages"
type: source
tags: [session, session-transcript, llm-wiki, claude, wikilinks, link-resolution, page-relocation, merge-behavior, filename-resolution, graph-consistency, filename-keying]
date: 2026-09-30
source_file: raw/sessions/llm-wiki/2026-09-07T23-12-llm-wiki-wikilink-resolution.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

The session established that wikilink resolution in llmwiki is based on filename stem, not folder path. This means pages can be safely relocated between folders without breaking links, as long as the filename remains unchanged. A test was added to validate this architectural design.

## Key Claims

- All wiki consumers (graph builder, backlink index, reference index, link lint rule) key pages by filename stem, not path
- Moving a page between folders is safe if the filename is unchanged
- Folder paths determine only a page's kind and its URL on the static site, not its identity in the knowledge graph

## Key Quotes

> "Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site."

This clarifies the separation of concerns: filenames drive link resolution and graph identity, while folder structure is purely organizational.

## Connections

- [[llmwiki]] (entity) — the system implementing filename-based link resolution
  - fact: All internal consumers key pages by filename stem, enabling safe page relocation.
- [[Wikilinks]] (concept) — cross-reference resolution mechanism
  - fact: Wikilink resolution depends on filename stem, not folder path, making pages relocatable.
- [[Knowledge Graph]] (concept) — the graph structure keyed by this design
  - fact: The knowledge graph uses filename stems as durable identifiers, independent of folder structure.
- [[Lint Rules]] (entity) — validation that uses filename keying
  - fact: Link lint rules validate references using filename stems, so they are unaffected by page relocation.