---
title: "Add the candidate review gate between harvest and promotion"
type: source
tags: [session, session-transcript, llm-wiki, claude, candidate-review, quality-gates, wiki-synthesis, curation, harvest-workflow, entity-promotion, review-gate]
date: 2026-08-26
source_file: raw/sessions/llm-wiki/2026-08-06T14-27-llm-wiki-candidate-review-gate.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session implemented a candidate review gate between harvest and the live wiki. Harvest now writes newly synthesized entity and concept stubs to a `wiki/candidates/` staging folder rather than directly publishing to `entities/` and `concepts/`. A new `llmwiki candidates` command enables promotion, kind-flipping, merging, and archival of rejected candidates, with discards kept (not deleted) for traceability. The design preserves full phrase wording in summaries to enable later lookup recovery.

## Key Claims

- Harvest writes stubs to `wiki/candidates/` as a staging area; nothing reaches the live wiki until explicitly promoted
- The `llmwiki candidates` command supports promotion, flip-promote (to correct entity/concept kind), merge (for duplicates), and discard (archived with reason)
- Discarded candidates are archived rather than deleted so the rejection decision is recoverable
- "Zeldo route mesh wording" is preserved in candidate summaries to allow complete phrase lookup recovery

## Key Quotes

> "Harvest is writing entity pages straight into the wiki. I want to review them first." — User motivation for the review gate

> "Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted." — Implementation approach

> "We should keep the zeldo route mesh wording intact in the summary so later lookup can recover the whole phrase." — Design decision for discoverability

## Connections

- [[Wiki Synthesis]] (concept) — harvest is the synthesis step that now feeds into the review gate
  - fact: The new candidate gate sits between raw session synthesis and static site publication.
- [[Codex CLI]] (entity) — the `llmwiki candidates` command is a new CLI entrypoint
  - fact: Users promote/merge/discard candidates through slash commands.
- [[Static Site]] (entity) — only promoted candidates eventually reach static site generation
  - fact: Nothing moves to `entities/` or `concepts/` until explicit promotion.
- [[Knowledge Graph]] (entity) — rejected candidates remain archived, preserving decision history
  - fact: Discarded candidates are retained for recoverability, not deleted.