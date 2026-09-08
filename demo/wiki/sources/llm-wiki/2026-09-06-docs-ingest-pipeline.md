---
title: "Ingest arbitrary documents alongside sessions"
type: source
tags: [session, session-transcript, llm-wiki, claude, docs-ingest, deduplication, immutability, incremental-sync]
date: 2026-09-06
source_file: raw/sessions/llm-wiki/2026-09-06T21-46-llm-wiki-docs-ingest-pipeline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session added a document ingest pipeline to [[llmwiki]] that extends the vault beyond session transcripts, allowing files, folders, and URLs to be converted to Markdown and ingested as immutable raw input. The system uses hash-based deduplication to prevent duplicate copies of unchanged documents, but creates new slugs when documents change rather than updating in-place—a known design limitation.

## Key Claims

- The ingest system accepts files, folders, or URLs and automatically converts them to Markdown for vault storage
- Ingested documents are stored as immutable raw input alongside session transcripts
- Hash-based deduplication prevents duplicate copies when unchanged documents are re-ingested
- When a document is updated, a new slug and copy are created; the original remains immutable
- In-place updates are intentionally not supported due to the immutability principle for raw input

## Key Quotes

> "Added an ingest path that takes a file, a folder or a URL, converts it to Markdown, and lands it beside the sessions as immutable input. It is then synthesised into a source page like anything else." — Establishes the core design of documents as first-class input sources alongside sessions.

> "Duplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy." — Describes the deduplication mechanism.

> "You get a second copy under a new slug, and the original stays. There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there." — Explains the update behavior and identifies the rough edge around document versioning.

## Connections

- [[llmwiki]] (project) — the system being extended to support non-session sources
  - fact: Document ingest expands the vault beyond session transcripts as the sole input source
  - fact: Ingested documents are synthesized into source pages using the standard pipeline
- [[Wiki Synthesis]] (process) — ingested documents follow the same synthesis workflow
  - fact: Documents are processed as immutable raw input and converted to synthesized pages
- [[Adapters]] (system) — document ingest functions as a new input adapter pattern
  - fact: Transforms files, folders, and URLs into standardized Markdown format for the vault
- [[Document Ingest]] (feature, new) — the capability added in this session
  - fact: Accepts files, folders, or URLs with automatic Markdown conversion
  - fact: Uses hash-based deduplication to prevent duplicate ingestion
  - fact: Maintains immutability by creating new slugs for changed documents
