---
title: "CLI reference (part 11/19: page-kinds — retype pages off the removed question/comparison kinds)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, migrations, page-schema, wikilinks]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation outlines four offline migration commands for [[llmwiki]]: `page-kinds` (retypes obsolete question/comparison pages to concepts and relocates them), `topic-kinds` (stamps entity/concept kinds onto older source Connections), `wikilink-titles` (adds display text to bare resolving links), and `discarded-topic-links` (introduced but not detailed). All migrations are idempotent, require no language model or network calls, and implement safety rules (collision detection, folder preservation) to prevent data loss.

## Key Claims

- Pages with `type: question` or `type: comparison` in frontmatter are validation errors; the `page-kinds` migration retypes them to `concept` and moves them to `wiki/concepts/` while keeping their filenames unchanged.
- Filenames are preserved during `page-kinds` migration to ensure inbound [[Wikilinks]] automatically remain valid, since links resolve by filename rather than folder location.
- The `page-kinds` migration refuses to overwrite existing files in the target folder; collision candidates are retyped in place and reported instead of silently failing.
- The `topic-kinds` migration stamps known entity/concept kinds onto older source Connections using only pages already on disk, without invoking a language model or network.
- Migration implementations live in the main package (not `scripts/`) so they work with standard pip or Homebrew installs without requiring a git checkout.

## Key Quotes

> "`[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing." — explains why preserving filenames during migration protects link integrity

> "no language model, no network call, and `raw/` is never written." — characterizes the offline, safe-to-repeat nature of migrations

> "a page whose filename is already taken in `wiki/concepts/` is retyped where it stands and reported as a collision rather than overwriting anything" — illustrates the conservative safety model

## Connections

- [[llmwiki]] (entity) — the primary subject
  - fact: Migration implementations are shipped in the main package so they work from standard installations
- [[Wikilinks]] (concept) — these migrations must preserve link semantics
  - fact: Wikilinks resolve by filename, so file-preserving migrations guarantee no inbound links break
- [[Lint Rules]] (concept) — migrations address schema validation
  - fact: Obsolete `question` and `comparison` types trigger `frontmatter_validity` errors; `page-kinds` clears them
  - fact: `page_findability` lint checks page title (frontmatter), not slug; `wikilink-titles` migration ensures display text includes titles
- [[Knowledge Graph]] (concept) — migrations update the interconnected page structure
  - fact: The `topic-kinds` migration connects Connections bullets to canonical entity/concept pages by stamping kinds