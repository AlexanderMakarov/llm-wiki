---
title: "Add the candidate review gate between harvest and promotion"
type: source
tags: [session, session-transcript, llm-wiki, claude, candidate-review, quality-gates, wiki-synthesis, curation, harvest-workflow, entity-promotion, review-gate]
date: 2026-08-29
source_file: raw/sessions/llm-wiki/2026-08-06T14-27-llm-wiki-candidate-review-gate.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Implemented a candidate review gate in [[llmwiki]] to prevent harvested entity stubs from reaching the wiki without human approval. Harvest now writes to `wiki/candidates/` instead of the destination folders, and a new `llmwiki candidates` subcommand enables human-controlled promotion through operations like promote, flip-promote (for kind correction), merge (deduplication), and archive-discard. Summary text is preserved intact to enable later phrase recovery during lookup.

## Key Claims

- Harvest now stages entity pages to `wiki/candidates/` folder instead of writing directly to `entities/` or `concepts/` folders
- A new `llmwiki candidates` subcommand provides review operations: promote (publish), flip-promote (correct entity kind when wrong), merge (combine duplicate stubs), and discard with archival
- Discarded candidates are archived rather than deleted, preserving the audit trail of review decisions for recoverability
- Summary fields are preserved intact in candidates to enable later search and phrase recovery

## Key Quotes

> "Harvest is writing entity pages straight into the wiki. I want to review them first." — establishes the problem of unreviewed direct publication

> "Discards are archived rather than deleted so the decision is recoverable." — design principle for non-destructive review workflows

## Connections

- [[llmwiki]] (entity) — the wiki tool enhanced with candidate review workflow
  - fact: Harvest ingestion now stages pages in a candidates folder pending human promotion
- [[Wiki Synthesis]] (concept) — the end-to-end process of extracting and aggregating documentation into wiki pages
  - fact: Candidate review introduces a new gate blocking automatic promotion of harvested stubs into published folders
- [[Candidate Review]] (concept) — new workflow system for human-in-the-loop review and promotion of harvested entity stubs
  - fact: Supports promote, flip-promote, merge, and archive-discard operations before pages reach the public wiki