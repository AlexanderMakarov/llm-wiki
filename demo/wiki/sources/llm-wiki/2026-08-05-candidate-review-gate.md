---
title: "Add the candidate review gate between harvest and promotion"
type: source
tags: [session, session-transcript, llm-wiki, claude, candidate-review, wiki-synthesis, harvest]
date: 2026-08-05
source_file: raw/sessions/llm-wiki/2026-08-05T14-27-llm-wiki-candidate-review-gate.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session implemented a candidate review gate in the wiki synthesis pipeline. Harvest now writes entity and concept stubs to `wiki/candidates/` instead of publishing directly to `entities/` and `concepts/` folders. A new `llmwiki candidates` command enables review operations: listing candidates, promoting to published, flipping incorrect kinds, merging duplicates, and discarding with archived reasons. The default threshold for candidacy is mentions in 3 distinct source pages (configurable via `--min-refs`).

## Key Claims

- Harvest writes to `wiki/candidates/` rather than directly to `entities/` or `concepts/` folders
- Pages must pass candidate review before entering the published wiki
- The default threshold for becoming a candidate is mentions in 3 distinct source pages, justified by the observation that single mentions are usually incidental
- The `llmwiki candidates` command supports promote, flip-promote (for kind correction), merge, and discard operations
- Discarded candidates are archived rather than deleted to preserve the recoverability of review decisions

## Key Quotes

> "Harvest is writing entity pages straight into the wiki. I want to review them first." — User, articulating the motivation for the review gate

> "Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted." — Core architectural change implementing the gate

> "A subject mentioned once is usually incidental, and promoting it produces a page with a single fact on it." — Justification for the 3-mention threshold mechanism

## Connections

- [[Wiki Synthesis]] (concept) — the core synthesis process enhanced with a review gate
  - fact: Harvest no longer writes directly to published folders; candidates must pass review before promotion
- [[llmwiki]] (system) — the main system implementing the review workflow
  - fact: The new `llmwiki candidates` command provides list, promote, flip, merge, and discard operations
- [[Candidate Review]] (concept) — the new review workflow for pages before publication
  - fact: Default candidacy threshold is 3 distinct source page mentions, configurable via `--min-refs`