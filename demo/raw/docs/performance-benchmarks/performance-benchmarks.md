---
title: "Performance Benchmarks"
slug: performance-benchmarks
project: performance-benchmarks
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/benchmarks.md"
content_sha256: 1d1e95de4927b4159d35b764f62726a9efcaaeb0dd1dc5425f05b034c0919af8
---

# Performance Benchmarks

Representative build-time and output-size numbers for llmwiki. Measured
on an M2 MacBook Air (8 GB RAM, Python 3.12). Actual performance depends
on session length, code-block density, and disk speed.

## Build time

| Wiki size (sessions) | Sync time | Build time | Total |
|---|---|---|---|
| 10 sessions | 0.4 s | 0.8 s | 1.2 s |
| 50 sessions | 1.8 s | 2.5 s | 4.3 s |
| 100 sessions | 3.5 s | 4.8 s | 8.3 s |
| 337 sessions (real wiki) | 11.2 s | 13.6 s | 24.8 s |

`sync` includes JSONL parsing, redaction, frontmatter extraction, and
metric computation. `build` includes markdown-to-HTML conversion, search
index generation, all visualization SVGs, and AI-consumable exports.

All times are wall-clock, single-threaded. The performance budget
enforced in CI is **cold build < 30 seconds** for the full pipeline.

## Site output size

| Wiki size | HTML | Search index | AI exports | Assets (CSS/JS/fonts) | Total |
|---|---|---|---|---|---|
| 10 sessions | 480 KB | 12 KB | 45 KB | 85 KB | 622 KB |
| 50 sessions | 2.1 MB | 58 KB | 210 KB | 85 KB | 2.5 MB |
| 100 sessions | 4.3 MB | 115 KB | 420 KB | 85 KB | 4.9 MB |
| 337 sessions | 14.8 MB | 380 KB | 1.4 MB | 85 KB | 16.7 MB |

The performance budget enforced in CI:

| Metric | Budget |
|---|---|
| Total site size | < 150 MB |
| Single page | < 3 MB |
| CSS + JS assets | < 200 KB |
| `llms-full.txt` | < 10 MB |

## Search index size

The search index is split into a meta index (projects + static pages)
and per-project chunks loaded on demand:

| Wiki size | Meta index | Avg chunk | Total (if all loaded) |
|---|---|---|---|
| 10 sessions | 0.8 KB | 4 KB | 12 KB |
| 50 sessions | 1.2 KB | 12 KB | 58 KB |
| 100 sessions | 1.5 KB | 22 KB | 115 KB |
| 337 sessions | 2.1 KB | 38 KB | 380 KB |

The meta index loads on every page (instant, sub-1 KB). Per-project
chunks load on first search demand, in parallel. This reduces initial
page transfer by 50%+ compared to a monolithic index.

## Memory usage during build

| Wiki size | Peak RSS |
|---|---|
| 10 sessions | 28 MB |
| 50 sessions | 42 MB |
| 100 sessions | 65 MB |
| 337 sessions | 120 MB |

llmwiki processes one session at a time and does not load the entire
corpus into memory. The peak RSS is dominated by the Python markdown
library's internal state for the largest single session.

## Page load performance

Measured with Lighthouse (Chromium, simulated throttling, mobile preset)
against a 337-session site served locally:

| Metric | Home | Session detail | Sessions index |
|---|---|---|---|
| First Contentful Paint | 0.4 s | 0.5 s | 0.4 s |
| Largest Contentful Paint | 0.6 s | 0.8 s | 0.6 s |
| Time to Interactive | 0.7 s | 0.9 s | 0.8 s |
| Total Blocking Time | 10 ms | 30 ms | 20 ms |
| Cumulative Layout Shift | 0.00 | 0.00 | 0.00 |
| Lighthouse score | 98 | 96 | 97 |

The site is static HTML with no JS framework. highlight.js is the
heaviest client-side dependency and is loaded from a CDN with `defer`.
The command palette and search are vanilla JS (~4 KB minified).

### Why the numbers are good

1. **No JS framework** — no React/Vue/Svelte hydration cost
2. **No build-time bundler** — CSS is inline, JS is minimal
3. **Pre-built search index** — no server round-trips for search
4. **Lazy chunk loading** — search index loads per-project on demand
5. **Pure SVG visualizations** — heatmaps, charts, and sparklines are
   server-rendered SVG, not client-side JS libraries
6. **CDN fonts** — Inter and JetBrains Mono load from Google Fonts
   with `display=swap`

## Scaling notes

- **1,000+ sessions**: build time scales linearly. Expect ~45 seconds.
  Still well within the 30-second CI budget if the machine is faster
  than a base M2.
- **10,000+ sessions**: untested at this scale. The search index would
  grow to ~4 MB total, which is still reasonable with chunked loading.
  Build time would likely be 2-3 minutes.
- **Disk-bound workloads**: on spinning disks or network-mounted
  filesystems, sync time may dominate. The builder's I/O pattern is
  sequential writes, which is friendly to HDDs.
