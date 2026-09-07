---
title: "Extract readable text from two-column PDFs"
type: source
tags: [session, session-transcript, paper-notes, claude, pdf-text-extraction, column-detection, layout-aware-parsing]
date: 2026-08-19
source_file: raw/sessions/paper-notes/2026-08-19T23-36-paper-notes-pdf-text-extraction.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Replaced a naive PDF text reader with column-aware extraction to fix interleaved text from two-column papers. The new approach detects column boundaries per-page from text block positions and reads each column sequentially, automatically handling mixed-layout documents like single-column abstracts followed by multi-column body sections.

## Key Claims

- The original reader traversed pages in raw order, causing text from adjacent columns to interleave into nonsensical output
- Column detection works per-page rather than document-wide, enabling elegant handling of mixed-layout papers without special cases
- Single-column pages are naturally supported since they are detected as one column spanning the full page width
- Text block positions serve as the signal for identifying column boundaries

## Key Quotes

> "The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on." — Explains the fundamental shift from naive sequential reading to layout-aware extraction.

> "Yes — detection runs per page rather than once per document, so a single-column abstract followed by two-column body works." — Demonstrates how per-page detection elegantly handles mixed-layout papers without special cases.

## Connections

- [[paper-notes]] (project) — research paper management and annotation system
  - fact: PDF text extraction with layout awareness is a core content ingestion feature

## Contradictions

None identified.