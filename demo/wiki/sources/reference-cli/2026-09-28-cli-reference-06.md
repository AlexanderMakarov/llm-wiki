---
title: "CLI reference (part 6/19: candidates — approval workflow)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, candidates-approval, link-rewriting, key-facts-synthesis, alias-resolution]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documents the `candidates` command subsystem for wiki page approval workflows. It covers seven actions—`list`, `promote`, `flip-promote`, `merge`, `discard`, `apply`, and `rewrite-key-facts`—for managing candidate pages from initial generation through promotion to trusted status. The system includes intelligent link rewriting when pages are discarded, automatic Key Facts population from source connections, batch operations with conflict detection, and integrations with the static site UI and reconciliation of wiki indices.

## Key Claims

- `--slug` matching attempts exact filename lookup first, then falls back to a normalized fold (case- and punctuation-insensitive) shared by `link_integrity` and harvest, disambiguating with explicit errors on multiple matches rather than silent guesses
- `promote` auto-fills empty `## Key Facts` sections from nested `fact:` bullets on Connections topics of cited source pages; this population step is offline and does not require a synthesis backend
- `merge` unions `sources:` metadata and Connections links from a candidate into a target page (trusted or peer pending stub) and records the merged name under `## Aliases` so inbound wikilinks resolve via the alias in graph and lint queries
- `discard` rewrites all wikilinks to the discarded name as plain text (preserving visible labels) unless `--redirect PAGE` converts them to aliases pointing to an existing live page; links are skipped if another live page or alias already claims the name
- `apply` executes a JSON batch of candidate actions atomically and refuses batches where the same slug is targeted by conflicting operations (e.g., merge into X and also promote X in the same batch)
- `rewrite-key-facts` on trusted pages requires the backend named by `synthesis.backend` and allows per-vault prompt override in `wiki/prompts/key_facts.md`

## Key Quotes

> "`promote` fills an empty (or heading-only) `## Key Facts` from nested `fact:` bullets on the cited source pages' Connections topics (#147 / #103). That path is offline — Dummy / `None` backends are fine."

Shows that Key Facts extraction from source pages is an offline mechanism independent of synthesis backend selection.

> "inbound `[[merged-away]]` links resolve to the survivor via that section in graph, lint, backlinks, and references"

Illustrates how alias records created during merge propagate through the entire wiki graph system.

> "Links are left alone when another live page or alias already answers to the name, and `--redirect` is then refused before the stub moves"

Enforces consistency: preventing duplicate live pages from answering to the same name.

## Connections

- [[llmwiki]] (entity) — The CLI tool providing the `candidates` command for approval workflow
  - fact: The candidates subsystem integrates seven actions (list, promote, flip-promote, merge, discard, apply, rewrite-key-facts) into an end-to-end page review and promotion pipeline

- [[Wikilinks]] (concept) — Link resolution and rewriting when candidates are discarded or merged
  - fact: Discard rewrites all `[[link]]` references to the discarded name as plain text (or redirects them to aliases) across all wiki pages that reference it

- [[Knowledge Graph]] (concept) — Alias records from merges and discards integrate into graph resolution
  - fact: Merged-away page names resolve through `## Aliases` sections in graph, lint, backlinks, and reference queries

- [[Wiki Synthesis]] (concept) — The synthesis backend powers the `rewrite-key-facts` action on trusted pages
  - fact: `rewrite-key-facts` is opt-in (not automatic on promotion) and configurable per vault via `wiki/prompts/key_facts.md`

- [[Static Site]] (entity) — The `site/candidates.html` UI provides the primary interface for reviewing candidates and batch-applying decisions
  - fact: The candidates UI prints the exact `candidates apply` command and JSON batch payload for rows a reviewer selects

- [[Lint Rules]] (concept) — The normalized slug fold used by `--slug` is shared with `link_integrity` and harvest checks
  - fact: Slug matching uses the same case- and punctuation-insensitive normalization as wiki consistency checks

## Contradictions

None identified; this documentation is consistent with existing references to candidates in issue tracking (#101, #103, #147, #149, #282).