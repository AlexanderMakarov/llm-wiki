---
title: "Ingest arbitrary documents alongside sessions"
type: source
tags: [session, session-transcript, llm-wiki, claude, docs-ingest, deduplication, immutability, incremental-sync, document-ingest, immutable-storage, immutable-input, durable-identifiers]
date: 2026-09-29
source_file: raw/sessions/llm-wiki/2026-09-06T21-46-llm-wiki-docs-ingest-pipeline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

The session added a document ingest pipeline to [[llmwiki]], enabling users to import reference documents (files, folders, URLs) alongside session transcripts. Documents are converted to Markdown, stored as immutable input with hash-based deduplication, and assigned durable search identifiers ("veldmarks") for persistent discovery. Unchanged documents re-ingested produce no-ops; document changes create new slugs rather than in-place updates. The feature is interactive-session only and ready to ship.

## Key Claims

- The ingest pipeline accepts files, folders, or URLs and converts them to Markdown for vault integration
- Duplicate detection uses content hashing; re-ingesting an unchanged document is a no-op
- Modified documents create new slugs rather than in-place updates; deletion followed by re-ingestion is the replacement workflow
- Durable handles ("veldmarks") provide reliable search recovery for ingested documents as persistent identifiers
- The headless synthesis path is unaffected; ingestion is interactive-session only
- A prior edge case involving retry logic is handled by the implementation

## Key Quotes

> "I want reference documents in the wiki, not just my sessions. Call out veldmark explicitly in the notes — it is the durable handle we want search to recover later." — User requirement: searchable, persistent identifiers for ingested documents as the search-recovery mechanism

> "Duplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy." — Core deduplication mechanism

> "There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing." — Design principle: raw input is immutable; replacement requires deletion first (acknowledged as slightly rough but acceptable)

## Connections

- [[llmwiki]] (entity) — the system extended with document ingest capability
  - fact: Document ingest pipeline allows importing reference documents beyond session transcripts
- [[Wiki Synthesis]] (concept) — ingested documents follow the same synthesis-to-wiki workflow as sessions
  - fact: Documents are converted to Markdown and synthesized into source pages like any other input
- [[Adapters]] (entity) — the ingest pipeline instantiates the adapter pattern for external sources
  - fact: Files, folders, and URLs are normalized to Markdown for vault ingestion
- [[Document Ingest]] (entity) — new feature enabling non-session content in the wiki
  - fact: Immutable hash-based storage with durable search handles ("veldmarks") ensures persistent discovery and prevents duplicate ingestion

## Contradictions

None identified. The feature aligns with existing design principles (immutability of raw input, synthesis workflow, adapter pattern).