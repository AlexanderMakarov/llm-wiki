---
title: "CLI reference (part 6/19: candidates — approval workflow)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, candidates-workflow, slug-matching, link-redirect, key-facts]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This page documents the `candidates` command—a multi-action approval workflow for promoting, merging, discarding, and rewriting wiki page candidates awaiting review. It covers 7 distinct actions, slug matching with case/punctuation-insensitive folding, automatic Key Facts synthesis, batch operations via JSON, and link redirect/archive mechanisms to maintain referential integrity when candidates are archived.

## Key Claims

- The `candidates` command supports 7 actions: `list`, `promote`, `flip-promote`, `merge`, `discard`, `apply`, and `rewrite-key-facts`.
- Slug matching uses exact filename match first; if no match, it falls back to a normalized `norm_page_key` fold (case and punctuation insensitive) and raises an error if the fold matches more than one page.
- `promote` can auto-fill empty `## Key Facts` from nested `fact:` bullets on source pages' Connections topics; non-empty reviewer Key Facts are left alone.
- `merge` combines two candidates by unioning their `sources:` and Connections links, recording the absorbed name under `## Aliases` so inbound links resolve via the survivor.
- `discard` archives a stub and rewrites every `[[link]]` to its name (outside `wiki/archive/`) as plain text or redirects them to an existing live page with `--redirect PAGE` and records the name as an alias.
- `apply` runs batches of the same action type in a single process (JSON array) and prevents conflicting operations—e.g., merging into a peer slug that the same batch also promotes is refused before any row runs.
- Successful actions reconcile `wiki/index.md` by dropping dead `candidates/…` bullets and listing newly trusted pages under Entities/Concepts.

## Key Quotes

> "A fold matching more than one page raises, naming every match, instead of guessing."
> — Ensures safe slug resolution; prevents silent misidentification when multiple pages normalize to the same key.

> "`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases`"
> — Shows how candidate merges maintain the knowledge graph via aliases, so links resolve correctly after consolidation.

> "`discard` archives the stub and rewrites every `[[link]]` to its name outside `wiki/archive/` (any casing, labels and anchors included) to plain text — … so no link points into cold storage"
> — Demonstrates link integrity discipline: dead links are preferred to orphaned references.

## Connections

- [[llmwiki]] (entity) — Core system implementing the candidates approval workflow.
  - fact: The `candidates` command is a major subsystem for editorial review of auto-generated candidate pages.

- [[Wiki Synthesis]] (concept) — Candidates are pending pages awaiting review before inclusion in the synthesis workflow.
  - fact: `promote` auto-fills Key Facts from source pages; `rewrite-key-facts` uses the synthesis backend to rewrite trusted pages' facts.

- [[Static Site]] (concept) — Candidates UI rendered at `site/candidates.html` for reviewer decisions.
  - fact: The Apply button prints the `candidates apply --vault … --actions -` command and JSON batch; a successful apply rebuilds `site/`.

- [[Wikilinks]] (concept) — Candidates system uses sophisticated link resolution for slug matching and link rewriting.
  - fact: Discard rewrites `[[link]]` references using the same `norm_page_key` fold as `link_integrity` and harvest, and respects labels/anchors.

- [[Knowledge Graph]] (concept) — Merge and discard operations maintain graph structure via Connections and Aliases.
  - fact: Merge unions Connections links; discard redirects can record names as aliases, allowing later links to resolve through the survivor.

- [[Lint Rules]] (concept) — Candidates system enforces link integrity and archive compliance.
  - fact: Slug matching and `link_integrity` both use the same case/punctuation-insensitive fold; discard prevents links from pointing into `wiki/archive/`.