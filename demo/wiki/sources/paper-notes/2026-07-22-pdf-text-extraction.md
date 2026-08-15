---
title: "Extract readable text from two-column PDFs"
type: source
tags: [session, session-transcript, paper-notes, claude, pdf-text-extraction, column-detection, reading-order, layout-aware-parsing]
date: 2026-07-22
source_file: raw/sessions/paper-notes/2026-07-22T23-36-paper-notes-pdf-text-extraction.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

Replaced a naive PDF text reader (which produced interleaved output in two-column documents) with a column-aware reader that detects column boundaries from text block positions and reads each column sequentially. Detection runs per-page, supporting mixed layouts (e.g., single-column abstract followed by two-column body).

## Key Claims

- The original reader processed text blocks in raw page order, causing interleaved nonsense in two-column layouts
- The new reader detects column boundaries by analyzing the spatial positions of text blocks
- Column detection runs per-page rather than once per document, enabling support for documents with mixed layouts
- Single-column pages are handled transparently (treated as one detected column equal to page width)

## Key Quotes

> "The reader walked the page in raw order." — explains why two-column extraction failed

> "It now detects column boundaries from text block positions and reads each column through before moving on." — describes the core fix

> "detection runs per page rather than once per document, so a single-column abstract followed by two-column body works." — shows how the per-page approach handles layout variation

## Connections

- [[PDF Text Extraction]] — the primary capability being improved
- [[Column Layout Detection]] — the key innovation (inferring column structure from block positions)