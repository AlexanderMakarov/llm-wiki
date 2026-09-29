---
title: "CLI reference (part 12/19: source-page-paths — move source pages filed under a stale name)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, offline-migration, link-rewriting, candidate-archive]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation describes the `migrate discarded-topic-links` command, an offline migration tool that consolidates or redirects inbound wikilinks when candidate pages are archived, with special guards to preserve merged-name relationships. A second command, `migrate source-page-paths`, is introduced but not fully detailed in this excerpt. Both operate without language models or network calls.

## Key Claims

- `migrate discarded-topic-links` converts stale wikilinks to archived candidates into plain text (using link labels where available) or redirects them to live pages via `--redirect NAME=PAGE` flags
- Candidates marked "merged into <target>" are protected: their links are preserved and the command exits 1 to force explicit handling, preventing accidental loss of merged-name relationships
- Every `--redirect` pair is validated before any writes occur; if errors exist, the command outputs `nothing was written: fix the errors above and re-run` and exits 1, ensuring atomicity
- The command is idempotent: re-running on an already-migrated vault reports no changes (`nothing to migrate: no links to discarded candidates and no nested stubs`)
- Both migrations run fully offline with no language models or network calls and support `--dry-run` for safe preview before applying changes

## Key Quotes

> "finds every archived candidate that no live page answers to (by stem or `## Aliases` — merged and redirected names are left alone) and turns each `[[Name]]`, `[[name|label]]` or `[[Name#section]]` outside `wiki/archive/` into plain text" — describes the core link-cleanup strategy

> "no language model, no network call, `raw/` never written" — key design principle: fully deterministic offline operation

> "A candidate a reviewer *merged* is archived with `Reason: merged into <target>`, and its links belong on the survivor page" — protection mechanism against losing merged-name relationships

> "Idempotent: a second run finds nothing to rewrite and prints `nothing to migrate`" — ensures safe, repeatable execution

## Connections

- [[llmwiki]] (entity) — this reference documents core CLI commands within the llmwiki system
  - fact: `migrate discarded-topic-links` is implemented in `llmwiki/migrate_discarded_topic_links.py` and invoked via the `llmwiki migrate` subcommand
- [[Lint Rules]] (concept) — offline migration resolves issues that the `link_integrity` lint check reports
  - fact: The command clears the backlog of broken wikilinks by unlinking or redirecting them to live pages
- [[Knowledge Graph]] (concept) — the command preserves and maintains the integrity of wikilink relationships
  - fact: Special guards ensure merged-name relationships are protected, pointing wikilinks to intended survivor pages rather than discarding the semantic target

## Contradictions

None identified.