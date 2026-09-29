---
title: "UI reference (part 6/8: Docs hub)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, ui-reference, analytics-dashboard, prototype-states, recent-documents, docs-hub]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-29
---
## Summary

This document specifies the UI design of four key pages in the reference-ui system: the Docs hub (editorial entry point), Prototypes hub (six review-ready UI states), Recent documents list (with collapsing of multi-part docs), and Analytics dashboard (combining session metrics, activity heatmaps, MCP telemetry, and "dead stock" tracking for unread sources).

## Key Claims

- The Prototypes hub displays six specific UI states (`page-shell`, `article-anatomy`, `drawer-browse`, `search-results`, `empty-search`, `references-rail`) for safe UX iteration before changes touch live templates
- Each prototype includes a 4 px `#7C3AED` top stripe and "Prototype — not a live page" disclaimer to prevent confusion with production pages
- The Recent page consolidates multi-part documents into single rows with part counts, collapsing e.g. `<slug>-01.md` through `<slug>-NN.md` in a folder into one entry
- Analytics page combines candidates review, activity heatmaps, recent log entries, project cards, MCP telemetry, and dead-stock tracking (collapsible listing of unread synthesized sources)
- Analytics tracks cumulative billed throughput including cache_read (not just context-window occupancy) and merges historical MCP data by folding retired tool names into canonical rows

## Key Quotes

> "Review-ready UI states for UX iteration **before** larger UI changes touch the live templates."

Establishes prototypes as staging areas for UX work, decoupled from live content.

> "Every prototype carries a **4 px `#7C3AED` top stripe** and a "Prototype — not a live page" meta block so reviewers never confuse them with real pages."

Design guard preventing accidental use of prototypes as production references.

## Connections

- [[llmwiki]] (entity) — this document specifies the reference UI pages that comprise the wiki's editorial, review, and analytics surfaces
  - fact: Docs hub is the editorial entry point compiled from the same synthesis pipeline as session pages; Analytics aggregates session metrics and MCP telemetry across the wiki.
- [[Wiki Synthesis]] (concept) — the pages are outputs from and display artifacts of the synthesis pipeline
  - fact: Recent and Analytics pages display synthesized session artifacts and their metadata.
- [[Static Site]] (concept) — all pages are static HTML served at fixed URLs without dynamic request handling
  - fact: Pages deployed at `/docs/index.html`, `/analytics.html`, `/recent.html`, and `/prototypes/index.html`.
- [[Observability]] (concept) — Analytics dashboard tracks session volume, token usage, cache performance, and MCP activity
  - fact: Analytics displays tokens per session, cache hit rates, 18-month GitHub-style activity heatmaps, and per-tool MCP call statistics.

## Contradictions

None identified.