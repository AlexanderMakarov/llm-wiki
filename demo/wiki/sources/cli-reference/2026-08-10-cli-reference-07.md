---
title: "CLI reference (part 7/8: migrate-page-kinds — retype pages off the removed question/comparison kinds (#109))"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, page-migration, knowledge-graph, provenance-tracing, wiki-schema]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

This document references eight CLI commands for the llmwiki tool, documenting commands for migrating deprecated page types, deduplicating topics via LLM, querying the knowledge graph, tracing page provenance to raw transcripts, and orchestrating the full build pipeline. Key design decisions include preserving filenames during migration (so [[wikilinks]] don't break), implementing tools in the package rather than scripts/ (for pip/Homebrew compatibility), and using only frontmatter for provenance chains to avoid brittleness.

## Key Claims

- Five canonical knowledge kinds exist: `source`, `entity`, `concept`, `project`, `synthesis`. Pages declaring `type: question` or `type: comparison` are schema errors.
- During `migrate-page-kinds`, pages are retyped to `concept` and moved into `wiki/concepts/`, but retain their original filename so existing [[wikilinks]] continue resolving without editing referring pages.
- `migrate-page-kinds` implements safety rules: pages whose new filename collides with existing `wiki/concepts/` entries are reported rather than overwritten; empty folders are pruned, but non-empty ones are left and reported.
- `consolidate-topics` merges duplicate topic spellings (e.g. `LLM-Wiki` / `LLMWiki` / `llm wiki`) via a single LLM pass and caches the result in `.llmwiki-topics.json` for consumption by `graph` and `build`.
- The `trace` command uses only frontmatter metadata (`sources:`, `source_file:`) to walk provenance chains; missing hops are marked but do not halt the walk.
- Commands like `migrate-page-kinds` are implemented in the package (not under `scripts/`) so they run from pip or Homebrew installations without requiring a checkout.

## Key Quotes

> "Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing."

This justifies the core safety property of migration: pages can be reorganized without cascading edits.

> "Implementation: `llmwiki/migrate_page_kinds.py` — in the package rather than under `scripts/`, so it runs from a pip or Homebrew install with no checkout."

This establishes the principle that distribution-friendly tools live in the package, not the development repository.

> "Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts. Missing hops are marked; the walk still succeeds."

This trade-off prioritizes robustness (frontmatter is stable) over completeness (body quotes would break if pages are edited).

## Connections

- [[LLM Wiki]] — documents the CLI surface of the llmwiki tool
- [[Page Schema]] — defines the five knowledge kinds and validation rules
- [[Knowledge Graph]] — several commands (`consolidate-topics`, `query`, `all`) build and query the graph
- [[Provenance]] — `trace` command exposes the chain from wiki pages back to raw sessions

## Contradictions

None identified. The document is reference material establishing CLI specifications and design rationale rather than making claims that could conflict with prior wiki entries.