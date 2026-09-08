---
title: "CLI reference (part 10/15: topic-kinds — stamp entity/concept kinds onto older source Connections)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, vault-migration, topic-kinds, broken-provenance, synth-state, wikilinks, wiki-synthesis]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the CLI reference documents three offline `llmwiki migrate` subcommands for vault maintenance after schema or sync changes. `topic-kinds` backfills `(entity)` and `(concept)` labels on `## Connections` bullets in older `wiki/sources/` pages by matching names to `wiki/entities/`, `wiki/concepts/`, and `wiki/candidates/`, without touching `raw/` or using an LLM. `broken-provenance` repairs or clears `source_file` / `sources:` hops that point at missing `raw/sessions/` files—especially after Cursor Agent CLI re-syncs that used a `store` stem—using same-calendar-day, interactive-only remapping rules. Both commands support `--dry-run`, are idempotent on success, and integrate with index/log updates and synth state so routine `llmwiki synth` does not re-bill rewrite-clear sources.

## Key Claims

- `llmwiki migrate topic-kinds` edits only the Connections section of wiki source pages; nested `fact:` lines, Key Claims, Key Quotes, and frontmatter remain byte-identical.
- Ambiguous wikilink targets that exist as both entity and concept are skipped and reported rather than guessed.
- A non-dry-run `topic-kinds` run that stamps at least one page writes vault-local `.llmwiki-topic-kinds-stamped.json` and upserts synth state for raw sessions whose wiki targets are rewrite-clear, including when many raw files share one synth filename.
- Stamping clears the rewrite-needed flag when at least one resolvable kind is applied but does not derive fact lines; fact lines require `llmwiki synth --force --path …` afterward.
- `llmwiki migrate broken-provenance` never remaps provenance across calendar days and never remaps to raw rows explicitly marked `is_headless: true`.
- Same-day remapping among multiple interactive candidates uses the uniquely closest `HH-MM` timestamp; ties or headless-only pools lead to clearing broken provenance instead of guessing.

## Key Quotes

> "no language model, no network call, and `raw/` is never written" — defines the offline, deterministic scope of `topic-kinds`.

> "Never remaps across days (that used to point every June stub at a single January session)" — documents the hard same-day constraint for `broken-provenance`.

> "The report always states that zero facts were derived." — separates kind stamping from synthesis of `fact:` bullets.

## Connections

- [[llmwiki]] (entity) — hosts `migrate topic-kinds` and `migrate broken-provenance` as named vault migrations under `llmwiki migrate`.
  - fact: Migrations reconcile `wiki/index.md` and append `## [YYYY-MM-DD] migrate | page kinds` (or equivalent migrate operation) to `wiki/log.md` when they change the vault.
- [[Wikilinks]] (concept) — Connection bullets use `[[page]]` targets; `topic-kinds` adds `(entity)` / `(concept)` disambiguators aligned with canonical topic pages.
  - fact: Already-kinded Connection bullets are left unchanged on re-run.
- [[Wiki Synthesis]] (concept) — stamping and provenance repair upsert synth state so plain `llmwiki synth` / `--estimate` avoids re-billing rewrite-clear sources tied to stamped or healed pages.
  - fact: Force resynthesis for fact lines on stamped pages uses `llmwiki synth --force --path …`.
- [[Cursor]] (entity) — `broken-provenance` targets wiki hops broken after Cursor Agent CLI re-sync when filesystem stem `store` was used as `sessionId` and older raw paths were deleted.
  - fact: Docs recommend a Cursor Agent CLI re-sync first so raw filenames carry real chat dates and `is_headless` is stamped.
- [[Adapters]] (concept) — session adapter behavior (interactive vs headless eligibility) gates which same-day raw files are valid remap targets for `broken-provenance`.
