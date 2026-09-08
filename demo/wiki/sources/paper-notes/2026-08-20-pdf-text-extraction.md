---
title: "Extract readable text from two-column PDFs"
type: source
tags: [session, session-transcript, paper-notes, claude, pdf-extraction, column-detection, text-processing, multi-column-layout]
date: 2026-08-20
source_file: raw/sessions/paper-notes/2026-08-20T23-36-paper-notes-pdf-text-extraction.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session addressed a PDF text extraction problem where naive line-by-line reading from multi-column papers produced interleaved, incoherent output. The solution implemented column-aware extraction that detects column boundaries from text block positions and reads each column sequentially before moving to the next. By running detection per-page rather than document-wide, the implementation gracefully handles documents with mixed layouts, such as single-column abstracts followed by multi-column body sections.

## Key Claims

- Naive PDF readers process pages in raw physical order, causing adjacent columns in multi-column layouts to interleave as incoherent text
- Column-aware extraction detects column boundaries by analyzing text block positions and reads each column completely before moving to the next
- Per-page column detection enables documents to mix single-column and multi-column sections without special handling
- Single-column pages are unaffected by column detection, since detecting one column is equivalent to processing the entire page

## Key Quotes

> "The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on." — Describes the core architectural shift from naive to column-aware reading.

> "Detection runs per page rather than once per document, so a single-column abstract followed by two-column body works." — Explains why the solution handles mixed layouts gracefully.

## Connections

- [[PDF]] (domain) — the file format being processed for text extraction
  - fact: Column boundaries must be detected from text block positions in PDF coordinate space

- [[Column Detection]] (technique) — the specific algorithm developed to solve interleaved text in multi-column layouts
  - fact: Per-page detection allows seamless mixing of single- and multi-column sections within one document

- [[Python]] (language) — the implementation language for the PDF extraction system
  - fact: The column-aware reader is implemented as a Python module processing academic papers

- [[Paper Notes]] (project) — the parent project improving PDF-to-markdown workflow
  - fact: Column-aware extraction addresses a core pain point in extracting readable text from academic papers
