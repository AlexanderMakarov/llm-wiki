---
title: "Performance Benchmarks"
type: source
tags: [wiki-add, raw-doc, session-transcript, benchmarks, build-pipeline, ci-budget, static-site, scaling]
date: 2026-09-28
source_file: 
project: benchmarks
model: 
last_updated: 2026-09-28
---
## Summary

This document establishes reference performance benchmarks for [[llmwiki]] measured on an M2 MacBook Air, showing that a 337-session production wiki builds in 24.8 seconds (11.2 s sync + 13.6 s build) and produces a 16.7 MB static site. The wiki enforces a hard CI budget of < 30 seconds cold build time and implements architectural optimizations—static HTML, lazy-loaded search chunks, server-rendered SVG—that deliver 98 Lighthouse score on pages. Scaling notes project linear performance out to 1,000+ sessions (~45 seconds build time).

## Key Claims

- The production wiki (337 sessions) achieves 24.8 seconds total build time: 11.2 s for sync (JSONL parsing, redaction, frontmatter, metrics) and 13.6 s for build (HTML, search index, visualizations, AI exports).
- The CI performance budget enforces cold build < 30 seconds; total site size < 150 MB; single page < 3 MB; CSS+JS assets < 200 KB; llms-full.txt export < 10 MB.
- Search index is split into a meta index (loads on every page, < 3 KB for 337 sessions) and per-project chunks loaded on demand, reducing initial page transfer by 50%+ vs. monolithic index.
- Peak memory usage (RSS) for the 337-session wiki is 120 MB; llmwiki processes one session at a time and does not load the entire corpus into memory.
- Page load performance on a 337-session site measured via Lighthouse: 0.4 s First Contentful Paint (home), 0.6 s Largest Contentful Paint (home), 0.7 s Time to Interactive (home), 98 Lighthouse score (home).
- The architecture uses static HTML with no JS framework (no React/Vue/Svelte), inline CSS, minimal vanilla JS (~4 KB), and server-rendered SVGs for visualizations; highlight.js is the heaviest client dependency, loaded from CDN with defer.
- Scaling estimates: 1,000+ sessions expect ~45 seconds build time; 10,000+ sessions would produce a ~4 MB search index but build time would likely reach 2–3 minutes.

## Key Quotes

> "The performance budget enforced in CI is **cold build < 30 seconds** for the full pipeline." — Establishes the hard constraint that gates deployments.

> "The site is static HTML with no JS framework. highlight.js is the heaviest client-side dependency and is loaded from a CDN with `defer`." — Core architectural choice that enables high Lighthouse scores.

> "This reduces initial page transfer by 50%+ compared to a monolithic index." — Justifies the search index chunking strategy.

> "llmwiki processes one session at a time and does not load the entire corpus into memory." — Design principle for memory efficiency.

## Connections

- [[llmwiki]] (entity) — these benchmarks measure the llmwiki build pipeline and output.
  - fact: Production wiki (337 sessions) builds in 24.8 seconds with < 30 s CI budget.
- [[Static Site]] (entity) — benchmarks quantify site output sizes and load performance.
  - fact: 337-session wiki produces 16.7 MB total static site; achieves 98 Lighthouse score.
- [[GitHub Actions]] (entity) — CI enforces performance budgets (build time, asset sizes) on every deployment.
  - fact: Performance budget enforced in CI: cold build < 30 seconds, total site < 150 MB.
- [[Wiki Synthesis]] (concept) — sync and build phases are the two stages measured in the benchmark.
  - fact: Sync time (JSONL parsing, redaction, metrics) and build time (HTML, search, exports) scale linearly with session count.

## Contradictions

None identified. This is reference documentation with no contradictions to existing wiki claims.