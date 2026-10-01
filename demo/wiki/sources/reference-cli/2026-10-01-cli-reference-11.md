---
title: "CLI reference (part 11/19: page-kinds — retype pages off the removed question/comparison kinds)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, page-kinds, topic-kinds, wikilink-titles, offline-migrations]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This reference documentation describes four offline CLI migration operations for the [[llmwiki]] system: retyping pages from removed `question` and `comparison` kinds to `concept`, stamping known entity/concept annotations onto source connections, adding title display text to bare wikilinks for findability, and managing links to discarded candidates. All migrations are idempotent, packaged for pip install, and can be previewed with `--dry-run` before applying.

## Key Claims

- Five knowledge kinds are defined in `llmwiki/schema.py`: `source`, `entity`, `concept`, `project`, `synthesis`
- Pages with `type: question` or `type: comparison` violate frontmatter_validity and must be retyped to `concept`, moved to `wiki/concepts/` while keeping filenames intact
- The `page-kinds` migration preserves all [[Wikilinks]] because link resolution uses filename, not folder path; referring pages require no edits
- The `topic-kinds` migration is fully offline — no LLM calls or network; it stamps known entity/concept kinds already present on disk in `wiki/entities/`, `wiki/concepts/`, and candidate folders
- The `wikilink-titles` migration is cosmetic, adding display text to bare `[[slug]]` links to improve readability and support title-based findability
- All migrations are implemented in the package (not `scripts/`), so they run from pip install with no checkout required
- Origin resolution for the `tools-used` adapter prefers vault `llmwiki-state.json` sync keys, falling back to glob by `sessionId`
- Safety rules prevent data loss: filename collisions stay in place and are reported; non-empty removed folders are not deleted

## Key Quotes

> "A hand-written page declaring `type: question` or `type: comparison` is a `frontmatter_validity` **error**, and this migration clears it"  
— Explains why the schema removed these kinds and what triggers the migration.

> "Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing."  
— Core design principle ensuring page renames don't break cross-references.

> "no language model, no network call, and `raw/` is never written"  
— Defining property of offline migrations (`topic-kinds`, `wikilink-titles`), contrasting with synthesis operations.

> "Idempotent: a second run finds nothing to migrate."  
— Safety guarantee across all migration operations.

## Connections

- [[llmwiki]] (entity) — core system undergoing schema and structural migrations
  - fact: Five knowledge kinds are defined in `llmwiki/schema.py`; `question` and `comparison` have been removed
  - fact: Migration implementations live in the package (e.g., `llmwiki/migrate_page_kinds.py`), not in scripts, enabling pip-install execution
- [[Wiki Synthesis]] (concept) — migrations reconcile wiki state and structure
  - fact: `page-kinds` migration updates `wiki/index.md` and appends timestamped entries to `wiki/log.md`
- [[Frontmatter]] (concept) — page-kinds migration enforces frontmatter validity rules
  - fact: Pages with `type: question` or `type: comparison` are frontmatter errors and must be retyped to `concept`
- [[Wikilinks]] (concept) — link resolution and title management through migrations
  - fact: Wikilink resolution uses filename, not folder, so page moves preserve all references automatically
  - fact: `wikilink-titles` migration adds display text to bare `[[slug]]` links for improved readability and findability
- [[Lint Rules]] (concept) — migrations interact with validation framework
  - fact: `frontmatter_validity` lint rule identifies and reports removed kinds before migration
  - fact: `page_findability` lint rule operates on page title (frontmatter), not slug or filename
- [[Knowledge Graph]] (concept) — topic-kinds migration annotates connection metadata
  - fact: `topic-kinds` migration stamps entity/concept kinds on existing Connections sections using only on-disk resolved pages
- [[Static Site]] (concept) — migrations affect wiki generation and output
  - fact: Site must be rebuilt after `page-kinds` or `wikilink-titles` migrations for HTML output to reflect changes

## Contradictions

None apparent. This is normative documentation of current system operations and schema.