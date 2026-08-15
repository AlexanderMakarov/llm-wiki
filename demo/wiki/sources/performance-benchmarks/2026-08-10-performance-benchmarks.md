---
title: "Performance Benchmarks"
type: source
tags: [wiki-add, raw-doc, session-transcript, performance-benchmarks, build-time, page-load-metrics, lazy-loading]
date: 2026-08-10
source_file: 
project: performance-benchmarks
model: 
last_updated: 2026-08-11
---
## Summary

This technical reference documents [[llmwiki]]'s build performance and output metrics across wiki sizes from 10 to 337 sessions. The full pipeline (sync + build) completes in 24.8 seconds on an M2 MacBook, with site output of 16.7 MB. Page load performance is excellent (Lighthouse 96–98) due to static HTML architecture and minimal JavaScript. The document outlines six architectural choices that enable these results and projects linear scaling to 1,000+ sessions (estimated 45s build time).

## Key Claims

- Full build pipeline for 337-session wiki completes in 24.8 seconds, within the <30s CI performance budget
- Total site output (HTML, search index, assets, AI exports) reaches 16.7 MB at 337 sessions, well below the 150 MB budget
- Page load performance is excellent (0.4–0.9s First/Largest Contentful Paint) with Lighthouse scores of 96–98, achieved without a JS framework
- Chunked, lazy-loaded search index reduces initial page transfer by 50%+ versus a monolithic index
- Peak RSS during build is 120 MB; the system processes sessions one at a time without loading the entire corpus into memory
- Linear scaling expected up to 1,000+ sessions; 10,000+ sessions untested but theoretically feasible (4 MB search index, 2–3 minute build)

## Key Quotes

> "llmwiki processes one session at a time and does not load the entire corpus into memory. The peak RSS is dominated by the Python markdown library's internal state for the largest single session." — demonstrates the efficient memory model

> "The site is static HTML with no JS framework. highlight.js is the heaviest client-side dependency and is loaded from a CDN with `defer`. The command palette and search are vanilla JS (~4 KB minified)." — explains the architectural foundation of good page load performance

> "cold build < 30 seconds" — the primary CI performance budget

## Connections

- [[llmwiki]] — the system being benchmarked; this establishes build-time and runtime performance baselines and CI budgets

## Contradictions

None. This is technical reference documentation establishing baseline metrics.