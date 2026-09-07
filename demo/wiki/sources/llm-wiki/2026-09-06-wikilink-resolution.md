---
title: "Confirm how cross-references resolve before moving pages"
type: source
tags: [session, session-transcript, llm-wiki, claude, wikilinks, link-resolution, page-relocation, alias-breaking]
date: 2026-09-06
source_file: raw/sessions/llm-wiki/2026-09-06T23-12-llm-wiki-wikilink-resolution.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Established that [[Wikilinks]] in [[llmwiki]] resolve by filename (stem) rather than by folder path, making page relocation between folders safe. Multiple systems—graph builder, backlink index, reference index, and lint rules—all use the file stem as the resolution key. However, merging pages breaks links because aliases are recorded but not consulted during link resolution.

## Key Claims

- Links resolve by filename (stem), not by folder path, making page relocation between folders safe
- Multiple systems (graph builder, backlink index, reference index, lint rules) all use the file stem as the resolution key
- A page's folder only determines its kind (category) and its URL on the site
- Page merging breaks existing links because recorded aliases are not consulted during link resolution

## Key Quotes

> "Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site." — Establishes that filename-based resolution makes page relocation safe.

> "Merging records the old name as an alias, but nothing consults aliases during resolution, so every existing reference to the merged-away name dangles." — Explains why page merging breaks links.

## Connections

- [[llmwiki]] (project) — The knowledge base system whose wikilink resolution mechanism is being examined.
  - fact: Filename-based resolution makes page relocation safe and enables flexible folder organization.
- [[Wikilinks]] (concept) — Resolve by filename (stem) rather than by folder path.
  - fact: Multiple systems (graph builder, backlink index, reference index, lint rules) use file stem for resolution.
- [[Knowledge Graph]] (concept) — Graph construction uses filename-based link resolution.
  - fact: Moving a page between folders does not break references because folder location doesn't determine page identity.