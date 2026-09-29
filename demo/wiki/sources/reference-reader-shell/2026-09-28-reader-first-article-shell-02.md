---
title: "Reader-first article shell (part 2/2: Live adopters (#285))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-reader-shell, infobox, frontmatter-configuration]
date: 2026-09-28
source_file: 
project: reference-reader-shell
model: 
last_updated: 2026-09-28
---
## Summary

Documents the reader-first article shell — an opt-in presentation feature for llmwiki pages (v1.1.0-rc8+) that automatically renders an infobox, table of contents, and references rail from existing frontmatter and wikilinks. The Claude Code entity page serves as the flagship live adopter, demonstrating how Wikipedia-style presentation aligns with structured entity metadata. Pages opt in by adding `reader_shell: true` to frontmatter and rebuilding.

## Key Claims

- The reader-shell is an opt-in feature configured via `reader_shell: true` in page frontmatter (available v1.1.0-rc8+)
- The shell automatically renders infobox + table of contents + references rail from existing page metadata without additional markup
- Project pages are seeded at build time via `llmwiki build --seed-project-stubs`, not committed to version control
- The Claude Code entity is the flagship live adopter, with pricing, benchmarks, and modality information mapping cleanly to Wikipedia-style infobox structure
- Implementation spans `llmwiki/reader_shell.py` and CSS in `llmwiki/render/css.py`, inheriting tokens from the brand system

## Key Quotes

> "The shell renders infobox + table of contents + references rail automatically from the page's existing frontmatter + wikilinks."
— Core behavior eliminating duplication between metadata and rendered output

> "Flagship model entity — infobox-worthy pricing, benchmarks, and modalities map cleanly to the Wikipedia-style shell"
— Rationale for Claude Code as the canonical live adopter

## Connections

- [[llmwiki]] (entity) — project implementing the reader-shell feature
  - fact: Renders infobox + TOC + references from frontmatter and wikilinks without additional markup
- [[Claude Code]] (entity) — flagship live adopter showcasing structured entity data
  - fact: Pricing, benchmarks, and modalities map to Wikipedia-style infobox layout
- [[Static Site]] (entity) — target output where reader-shell renders its presentation layer
- [[Wikilinks]] (concept) — cross-references automatically rendered in the reference rail