---
title: "Ingest arbitrary documents alongside sessions"
type: source
tags: [session, session-transcript, llm-wiki, claude, document-ingest, content-deduplication, immutability, versioning]
date: 2026-08-08
source_file: raw/sessions/llm-wiki/2026-08-08T21-46-llm-wiki-docs-ingest-pipeline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session added a document ingest pipeline to [[llm-wiki]] that accepts files, folders, or URLs as input, converts them to Markdown, and stores them as immutable raw input alongside transcripts. Documents are deduplicated by content hash to prevent redundant ingestion. Updated documents generate new copies under new slugs rather than overwriting existing entries—a design that preserves immutability but is acknowledged as rough for users wanting in-place updates.

## Key Claims

- The document ingest pipeline accepts files, folders, and URLs and converts them to Markdown format
- Duplicate detection is hash-based; re-ingesting an unchanged document is a no-op, not a duplicate copy
- Documents are stored as immutable raw input, following the same pattern as session transcripts
- When a document changes, a new slug and copy are created; the original is never overwritten
- Removal followed by re-addition is the current workaround for replacing a document

## Key Quotes

> "Added an ingest path that takes a file, a folder or a URL, converts it to Markdown, and lands it beside the sessions as immutable input. It is then synthesised into a source page like anything else."
> — Core feature: documents flow through the same synthesis pipeline as session transcripts.

> "Duplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy."
> — Deduplication prevents storage waste from unchanged documents.

> "There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing."
> — Design trade-off: immutability guarantees at the cost of update friction.

## Connections

- [[llm-wiki]] — extended to accept reference documents beyond transcripts

## Contradictions

None identified.