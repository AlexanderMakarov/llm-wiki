---
title: "CLI reference (part 10/15: topic-kinds — stamp entity/concept kinds onto older source Connections)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, migrate-commands, topic-stamping, provenance-repair, vault-maintenance]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-10.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This reference documents three offline migration utilities for [[llmwiki]] vault maintenance: `migrate page-kinds` classifies source pages, `migrate topic-kinds` stamps entity/concept kinds onto older [[Wikilinks|Connections]] without LLM calls, and `migrate broken-provenance` repairs wiki pages pointing to deleted raw session files by remapping or clearing broken hops to same-day alternatives. All three are idempotent and vault-local; none invoke the language model or modify `raw/`.

## Key Claims

- The `topic-kinds` migration stamps known entity/concept kinds from disk without network calls or language model invocation, resolving ambiguous names (existing as both entity and concept) by skipping them rather than guessing.
- The `broken-provenance` migration remaps wiki source file references to same-day interactive raw files when raw session paths have been deleted, and clears broken hops when no eligible alternative exists.
- All three migrations are idempotent: a second run on an unchanged vault reports "nothing to migrate" and makes no changes.
- A successful non-dry-run `topic-kinds` that stamps at least one page writes `.llmwiki-topic-kinds-stamped.json` vault-local machine state to permit selective re-synthesis.
- Stamping clears the rewrite-needed flag when kind lands, but does not invent [[Knowledge Graph|facts]]; explicit fact synthesis requires `--force --path` after stamping.

## Key Quotes

> "Older source summaries often list `[[wikilinks]]` under `## Connections` without an `(entity)` or `(concept)` kind."

— The problem motivating the `topic-kinds` migration.

> "no language model, no network call, and `raw/` is never written"

— Key property of offline migrations enabling safe, deterministic vault repairs.

> "Names that exist as both an entity and a concept are ambiguous: those bullets are skipped and listed in the report rather than guessed."

— Explicit uncertainty handling in stamping logic.

## Connections

- [[llmwiki]] (entity) — the wiki system these offline migrations maintain
  - fact: Three migration utilities (`page-kinds`, `topic-kinds`, `broken-provenance`) operate offline on vault structure without LLM or network access.
- [[Wikilinks]] (concept) — topic connections that `topic-kinds` stamps with entity/concept kinds
  - fact: The `topic-kinds` command resolves kinds from `wiki/entities/`, `wiki/concepts/`, and matching `wiki/candidates/` folders.
- [[Knowledge Graph]] (concept) — structured topic relationships managed by migrations
  - fact: Stamping clears the rewrite-needed flag when kinds land, permitting selective re-synthesis of facts.
- [[Configuration Reference]] (entity) — part of a 15-part CLI reference series
  - fact: This is part 10 of 15 of the CLI reference documentation.

## Contradictions

- None noted.