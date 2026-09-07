---
title: "CLI reference (part 5/15: candidates — approval workflow)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, candidates, approval-workflow, batch-apply, key-facts]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-05.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This is a reference document for the `candidates` CLI command, which orchestrates the approval workflow for pending wiki pages. It describes seven actions (list, promote, flip-promote, merge, discard, apply, rewrite-key-facts) for reviewing, promoting, consolidating, or rejecting candidate pages. The key feature is the batch `apply` action, which validates that all intended operations are conflict-free before executing them and automatically reconciles the wiki index.

## Key Claims

- `promote` populates an empty `## Key Facts` section from nested `fact:` bullets on the cited source pages' Connections topics (#147/#103).
- `merge` folds a harvest stub into a target page by unioning `sources:` and Connections links, and records the absorbed name under `## Aliases` for graph/backlink resolution.
- Batch operations in `apply` are rejected (before any row runs) if they contain conflicts—e.g., promoting and merging the same slug in the same batch (#149).
- A successful `apply` rebuilds `site/` by default (making `site/candidates.html` drop just-processed rows), but `--no-rebuild` skips this to allow multiple batches before a final build.
- `rewrite-key-facts` uses the backend named by `synthesis.backend` and can override prompts per vault via `wiki/prompts/key_facts.md`.
- The Site UI at `site/candidates.html` auto-generates the `candidates apply` command with the JSON batch for user-selected rows.

## Key Quotes

> "Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101): dead `candidates/…` bullets are dropped, an empty `## Candidates` section is removed, and newly trusted pages are listed under Entities/Concepts."

This highlights the tight coupling between candidate actions and wiki structure maintenance.

> "`promote` fills an empty (or heading-only) `## Key Facts` from nested `fact:` bullets on the cited source pages' Connections topics (#147 / #103). That path is offline — Dummy / `None` backends are fine."

Shows that promote can work without a live synthesis backend, relying on human-authored facts in sources.

> "A batch that merges into a peer slug the same batch also promotes, flip-promotes, discards, or merges away is refused before any row runs — the CLI prints the conflicting actions and exits non-zero (#149)."

Demonstrates safety validation in batch mode.

## Connections

- [[llmwiki]] (system) — the project and CLI tool being documented
  - fact: The candidates workflow is part of llmwiki's approval and consolidation system.
- [[Wiki Synthesis]] (concept) — `rewrite-key-facts` uses the synthesis backend to generate or refresh Key Facts
  - fact: The backend is named by `synthesis.backend` config and can be overridden per vault.
- [[Configuration Reference]] (doc) — `synthesis.backend` and `wiki/prompts/key_facts.md` are configuration points
- [[Knowledge Graph]] (concept) — candidates are pending nodes in the wiki's graph; merge creates aliases for backlink resolution
- [[Wikilinks]] (concept) — merge records absorbed names under `## Aliases` so inbound `[[merged-away]]` links resolve via the target page

## Contradictions

None identified.