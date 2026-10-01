---
title: "CLI reference (part 13/19: broken-provenance — remap or clear hops to missing raw sessions)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, source-page-migration, provenance-repair, wikilinks-maintenance]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Documents two maintenance commands for the [[llmwiki]] system: `migrate source-page-paths` relocates source pages to derived paths while rewriting wikilinks and managing frontmatter state, and `migrate broken-provenance` repairs references to deleted raw sessions by remapping to same-day interactive files or clearing broken links. Both commands support dry-run preview and are idempotent.

## Key Claims

- Source page path migration moves pages to derived locations based on their source file paths, keeping multi-part documents together as a group
- Link rewriting uses bidirectional backlinking to disambiguate wikilink targets when multiple pages share the same stem
- The `migrate broken-provenance` command remaps only to same-day interactive sessions to prevent incorrect cross-temporal associations
- Migration state is tracked in `synth.files` within the vault's `llmwiki-state.json` to distinguish between stale and freshly-converted pages
- Both commands are idempotent and can be previewed with `--dry-run` before committing changes

## Key Quotes

> "When more than one page answers to a bare stem, the link (or `sources:` entry) in page P follows the one source page with that stem whose body links back to P"
— Demonstrates sophisticated link disambiguation using bidirectional backlinking within the wiki graph

> "Never remaps across days (that used to point every June stub at a single January session)"
— Clarifies a critical safeguard against remapping references across unrelated calendar days

> "Prefer a Cursor Agent CLI re-sync first so raw filenames carry real chat dates and `is_headless` is stamped"
— Recommends ensuring raw session metadata is current before running the migration

## Connections

- [[llmwiki]] (entity) — the wiki system managing source pages and raw session files
  - fact: Both migration commands operate on vault directories containing `wiki/` and `raw/` subdirectories
- [[Wiki Synthesis]] (concept) — the process of converting raw sessions into wiki pages
  - fact: These migrations repair inconsistencies between raw source files and synthesized wiki pages that arise from file reorganization or session deletion
- [[Wikilinks]] (concept) — cross-reference syntax requiring updates during migrations
  - fact: Commands rewrite wikilink references across the entire wiki when pages are moved or source provenance changes
- [[Frontmatter]] (concept) — metadata including `source_file:` and `sources:` tracking page provenance
  - fact: Frontmatter is updated during migrations and synth state is recorded to track whether a source has been re-converted after synthesis
- [[Knowledge Graph]] (concept) — the interconnected structure of wiki pages
  - fact: Link rewriting preserves the knowledge graph by maintaining correct references when source pages are relocated or remapped