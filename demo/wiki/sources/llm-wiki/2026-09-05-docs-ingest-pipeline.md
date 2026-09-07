---
title: "Ingest arbitrary documents alongside sessions"
type: source
tags: [session, session-transcript, llm-wiki, claude, document-ingest, immutable-storage, content-deduplication, versioning]
date: 2026-09-05
source_file: raw/sessions/llm-wiki/2026-09-05T21-46-llm-wiki-docs-ingest-pipeline.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session implemented a document ingest pipeline for [[llmwiki]], allowing the wiki to incorporate arbitrary reference documents alongside session transcripts. Documents from files, folders, or URLs are automatically converted to Markdown and stored as immutable raw input, then synthesized into wiki pages. Content deduplication via hash prevents redundant copies; changed documents create new versioned copies under the immutability constraint, which was identified as a rough edge needing improvement.

## Key Claims

- The document ingest pipeline accepts files, folders, or URLs as input sources for the wiki
- Documents are converted to Markdown and stored as immutable raw input alongside sessions
- Duplicate documents are detected by content hash; re-adding an unchanged document is a no-op
- Changed documents create new copies with new slugs rather than updating in-place, preserving immutability of raw input
- Removing the original document first is the current workaround to replace an existing document

## Key Quotes

> "Added an ingest path that takes a file, a folder or a URL, converts it to Markdown, and lands it beside the sessions as immutable input. It is then synthesised into a source page like anything else." — Describes extending the wiki beyond session transcripts to accept reference documents

> "Duplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy." — Establishes content-addressed deduplication as the design principle

> "There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing." — Identifies versioning constraint and UX friction point

## Connections

- [[llmwiki]] (system) — Core system extended to accept arbitrary documents via multi-source ingest pipeline
- [[Wiki Synthesis]] (concept) — Ingested documents flow through the same synthesis pipeline as sessions to produce wiki pages

## Contradictions

None identified.