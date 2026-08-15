---
title: "Add the candidate review gate between harvest and promotion"
type: source
tags: [session, session-transcript, llm-wiki, claude, candidate-review, harvest-pipeline, mention-thresholds]
date: 2026-07-08
source_file: raw/sessions/llm-wiki/2026-07-08T14-27-llm-wiki-candidate-review-gate.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session implemented a review gate between harvest and wiki publication. Harvest now writes entity/concept stubs to `wiki/candidates/` instead of directly to `entities/` or `concepts/`, preventing publication until explicit review. A new `llmwiki candidates` CLI command enables listing, promoting, merging, category-flipping, and discarding candidates (archived for auditability). Candidacy itself is gated by mention frequency—entities must be referenced in at least three distinct source pages by default, lowerable via `--min-refs`.

## Key Claims

- Harvest writes to `wiki/candidates/` staging folder instead of directly to the destination folders; nothing is published until promoted
- Entities require citations from three distinct source pages to become candidates by default (configurable via `--min-refs`)
- The review interface supports promote, flip-promote (correct misclassified kind), merge (deduplicate), and discard operations
- Discards are archived rather than deleted, preserving decisions for later recoverability

## Key Quotes

> "Nothing reaches `entities/` or `concepts/` until it is promoted." — establishes the review gate as a hard boundary

> "A subject mentioned once is usually incidental, and promoting it produces a page with a single fact on it." — justifies the mention-frequency threshold to prevent low-signal entities

## Connections

- [[Wiki Synthesis]] — Candidate Review is a quality control gate in the synthesis pipeline