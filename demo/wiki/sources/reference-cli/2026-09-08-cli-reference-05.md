---
title: "CLI reference (part 5/15: candidates — approval workflow)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, candidate-approval, key-facts-promotion, wiki-index-reconciliation, merge-aliases, candidate-review, wiki-index-sync]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents the `llmwiki candidates` approval workflow: positional actions `list`, `promote`, `flip-promote`, `merge`, `discard`, `apply`, and `rewrite-key-facts`. Successful review actions reconcile `wiki/index.md` without requiring a separate `sync` or `synth` pass, and `apply` can run batched JSON decisions (including from `site/candidates.html`) with optional automatic `site/` rebuild. `promote` can populate empty **Key Facts** offline from `fact:` bullets on linked source topics; `merge` unions metadata and records **Aliases** so retired wikilinks still resolve; conflicting rows in one `apply` batch are rejected before any mutation.

## Key Claims

- After `promote`, `flip-promote`, `merge`, `discard`, or a successful `apply`, the CLI reconciles `wiki/index.md`: dead `candidates/…` entries drop, empty `## Candidates` is removed, and promoted pages appear under Entities or Concepts (#101).
- `/wiki-candidates` should invoke the same candidate actions; idle `sync`/`synth` is not the right way to refresh the catalog after review.
- `promote` fills an empty or heading-only `## Key Facts` from nested `fact:` bullets on cited sources’ Connections topics (#147 / #103); that path needs no LLM backend, and non-empty reviewer Key Facts are not overwritten.
- `merge` folds a stub into a target by unioning `sources:` and Connections links, appends reviewer prose under `## Candidate merge — <date>` when present, and lists the old name under `## Aliases` so inbound `[[merged-away]]` links resolve in graph, lint, backlinks, and references.
- `apply` executes a JSON batch in one process; if the batch would merge into a slug that the same batch also promotes, flip-promotes, discards, or merges away, the CLI prints conflicts and exits non-zero before running any row (#149).
- Successful `apply` rebuilds `site/` by default so `candidates.html`, Home, and Analytics match the wiki; `--no-rebuild` skips that when applying multiple batches before one `llmwiki build`.
- `rewrite-key-facts` refreshes machine-assembled Key Facts (or legacy merge blocks) using `synthesis.backend`, with per-vault prompt override at `wiki/prompts/key_facts.md`.

## Key Quotes

> "Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101)" — index maintenance is bundled into candidate decisions, not a follow-up pipeline step.

> "/wiki-candidates should call these same actions — do not run idle `sync`/`synth` just to refresh the catalog after review." — agent slash command and CLI share one workflow.

> "A batch that merges into a peer slug the same batch also promotes, flip-promotes, discards, or merges away is refused before any row runs" — batch safety (#149).

## Connections

- [[llmwiki]] (entity) — hosts the `candidates` subcommand and documents flags, defaults, and examples for vault operators.
  - fact: `candidates apply` accepts `--actions` JSON or stdin `-` and defaults to rebuilding `site/` after success.
- [[Wiki Synthesis]] (concept) — harvest produces pending stubs under `wiki/candidates/` that this workflow promotes, merges, or discards into trusted entity/concept pages.
  - fact: `rewrite-key-facts` depends on `synthesis.backend` for opt-in LLM rewrites of Key Facts.
- [[Static Site]] (concept) — `site/candidates.html` lists pending rows, captures per-row decisions, and prints the matching `candidates apply` command and JSON for **Apply** (#97).
  - fact: default post-`apply` rebuild keeps the candidates page and analytics widgets aligned with wiki state.
- [[Wikilinks]] (concept) — Connections `fact:` bullets feed offline Key Facts on promote; merge **Aliases** preserve resolution for links to retired slugs.
  - fact: merge alias behavior is shared across graph, lint, backlinks, and references.
- [[Knowledge Graph]] (concept) — merge survivor semantics and alias resolution affect how the graph treats merged-away names.
- [[CLAUDE.md]] (concept) — `/wiki-candidates` in the agent kit should mirror these CLI actions rather than re-ingesting via sync/synth.
