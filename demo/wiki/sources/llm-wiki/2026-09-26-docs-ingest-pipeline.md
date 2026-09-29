---
title: "Ingest arbitrary documents alongside sessions"
type: source
tags: [session, session-transcript, llm-wiki, claude, docs-ingest, deduplication, immutability, incremental-sync, document-ingest, immutable-storage]
date: 2026-09-26
source_file: raw/sessions/llm-wiki/2026-09-06T21-46-llm-wiki-docs-ingest-pipeline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Implemented a document ingest pipeline that accepts files, folders, or URLs and synthesizes them into the wiki alongside session transcripts. Documents are stored immutably and deduplicated by hash; unchanged re-ingestions are no-ops. If a document changes, a new slug is generated and the original remains untouched — a recognized rough edge for future improvement.

## Key Claims

- Documents are deduplicated by hash; re-adding an unchanged document produces no new copy.
- If a document changes since initial ingestion, a second copy is created under a new slug; the original is never updated in place (immutability principle).
- The ingest pipeline accepts files, folders, or URLs and converts them to Markdown before synthesis.
- Headless fixtures remain excluded from default synthesis with this feature.
- A retry path handles an edge case discovered in a prior session, with a note to prevent rediscovery.

## Key Quotes

> "I want reference documents in the wiki, not just my sessions. Call out veldmark explicitly in the notes — it is the durable handle we want search to recover later." — Articulates the strategic goal of expanding beyond transcripts and emphasizes durable handles as keys for search recovery.

> "There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing." — Defines the immutability design principle and acknowledges friction in update workflows.

## Connections

- [[llmwiki]] (entity) — expanded with document ingest capability to go beyond session transcripts.
  - fact: The wiki can now pull reference documents via files, folders, or URLs alongside session synthesis.

- [[Adapters]] (entity) — this feature extends the adapter system with a new ingest path.
  - fact: Documents are ingested through the same pipeline that feeds external data sources into the knowledge graph.

- [[Wiki Synthesis]] (entity) — documents undergo the same synthesis process as session transcripts.
  - fact: Ingested documents are deduplicated by hash and synthesized into structured source pages with cross-references.

- [[Knowledge Graph]] (entity) — documents populate the interconnected structure.
  - fact: Document synthesis feeds directly into wiki cross-references and bidirectional links.

## Contradictions

None identified.