---
title: "Extract readable text from two-column PDFs"
type: source
tags: [session, session-transcript, paper-notes, claude, pdf-extraction, column-detection, text-processing, multi-column-layout, layout-analysis, document-processing]
date: 2026-09-09
source_file: raw/sessions/paper-notes/2026-08-20T23-36-paper-notes-pdf-text-extraction.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Improved PDF text extraction in the paper-notes project to correctly handle multi-column academic papers. The original implementation read pages in raw order, interleaving text from different columns. The solution detects column boundaries from text block positions and processes each column sequentially. Column detection runs per-page, enabling support for documents with mixed layouts (e.g., single-column abstract followed by two-column body). Test suite verifies the behavior across multiple scenarios.

## Key Claims

1. The original PDF reader processed pages in raw order, causing text from adjacent columns to interleave into nonsensical output.
2. The revised implementation detects column boundaries from text block positions and reads each column through before moving to the next.
3. Single-column pages remain unaffected because one detected column represents the entire page.
4. Column detection runs per-page rather than per-document, allowing papers to mix layouts within a single document.
5. Behavior is locked down with comprehensive test cases that continue to pass.

## Key Quotes

> "The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on." — Core change from naive sequential reading to column-aware extraction.

> "detection runs per page rather than once per document, so a single-column abstract followed by two-column body works." — Explains why per-page detection handles variable layouts correctly.

## Connections

- [[paper-notes]] (entity) — Research paper management project involving PDF text extraction and document processing
  - fact: Implemented column-aware text extraction to preserve reading order in multi-column academic papers

## Contradictions

None identified.