---
title: "Extract readable text from two-column PDFs"
type: source
tags: [session, session-transcript, paper-notes, claude, pdf-extraction, column-detection, text-processing, multi-column-layout, layout-analysis, document-processing, reading-order, adaptive-layout]
date: 2026-09-12
source_file: raw/sessions/paper-notes/2026-08-20T23-36-paper-notes-pdf-text-extraction.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

This session addressed a PDF text extraction bug where multi-column academic papers were producing interleaved, unreadable output. The solution implemented column-aware text extraction that detects column boundaries from text block positions and reads each column sequentially before moving to the next. The detector runs per-page, allowing documents with mixed layouts (e.g., single-column abstract followed by two-column body) to be handled correctly. All tests pass and lint is clean.

## Key Claims

- The original PDF text extractor read pages in raw order, causing adjacent columns to interleave into nonsensical text.
- The new implementation detects column boundaries from text block positions to infer correct reading order.
- Detection runs per-page rather than per-document, enabling mixed-layout documents to be processed correctly.
- Single-column pages are unaffected (one detected column equals the full page).

## Key Quotes

> "The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on." — Core explanation of the fix

> "Detection runs per page rather than once per document, so a single-column abstract followed by two-column body works." — Describes adaptive layout handling

## Connections

This session is focused on PDF text extraction for the `paper-notes` project and does not connect to existing wiki topics.