---
title: "Add the candidate review gate between harvest and promotion"
type: source
tags: [session, session-transcript, llm-wiki, claude, candidate-review, quality-gates, wiki-synthesis, curation]
date: 2026-08-06
source_file: raw/sessions/llm-wiki/2026-08-06T14-27-llm-wiki-candidate-review-gate.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session added a candidate review gate between harvest and wiki promotion. Harvest now writes entity and concept stubs to `wiki/candidates/` instead of directly publishing, enabling review before pages go live. The workflow includes operations (list, promote, flip-promote, merge, discard) via the `llmwiki candidates` command, with discarded candidates archived for decision traceability.

## Key Claims

- Harvest writes entity and concept stubs to `wiki/candidates/` instead of directly publishing to `entities/` or `concepts/`
- No candidate reaches the main wiki until explicitly promoted through the review workflow
- Review operations via `llmwiki candidates`: list, promote, flip-promote (when entity kind is incorrect), merge (for duplicate stubs), discard (with reasons)
- Discarded candidates are archived rather than deleted, preserving the rationale for rejection
- Candidacy requires a minimum mention count across distinct source pages (default 3, adjustable via `--min-refs`)
- Single-mention subjects are typically incidental and produce low-value pages with minimal factual content

## Key Quotes

> "Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted." — Establishes the mandatory review-before-publication pattern

> "Review happens through `llmwiki candidates`: list, promote, flip-promote when the kind is wrong, merge when two stubs describe the same subject, discard with a reason." — Describes the candidate workflow operations

> "A subject mentioned once is usually incidental, and promoting it produces a page with a single fact on it." — Justifies the minimum reference count threshold for candidacy

## Connections

- [[Wiki Synthesis]] (process) — Candidate review is a new quality gate within the synthesis pipeline
  - fact: Harvest now writes to a staging folder instead of directly publishing entities and concepts

- [[Knowledge Graph]] (system) — Candidate review improves graph quality by filtering low-coverage subjects before they become nodes
  - fact: Minimum reference count of 3 ensures subjects have sufficient coverage before candidacy

- [[Codex CLI]] (interface) — The `llmwiki candidates` command exposes the review workflow
  - fact: Supports promote, flip-promote, merge, discard, and list operations

- [[llmwiki]] (project) — The main system receiving this curation layer
  - fact: Candidate review is now mandatory before entities and concepts reach the published wiki
