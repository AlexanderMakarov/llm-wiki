---
title: "Cache tiers — load-priority frontmatter"
type: source
tags: [wiki-add, raw-doc, session-transcript, cache-tiers-load-priority-frontmatter, token-budget, context-optimization, wiki-loading]
date: 2026-08-10
source_file: 
project: cache-tiers-load-priority-frontmatter
model: 
last_updated: 2026-08-11
---
## Summary

This document introduces the cache-tiers feature (shipped v1.2.0, issue #52), an optional frontmatter field that signals to `/wiki-query` how eagerly to preload wiki pages during context building. Four tiers (L1: always; L2: summary-only; L3: on-demand, the default; L4: archived) let authors explicitly declare load priority, controlling token spend without requiring pages to opt out. The feature is backward-compatible, preserves existing wiki semantics for unmarked pages, and includes linting rules and a Python API for integration.

## Key Claims

- Cache tiers are declared via `cache_tier: L1|L2|L3|L4` in page frontmatter; pages without the field default to L3 (on-demand) and behave identically to pre-feature wikis
- L1 pages are loaded in full on every `/wiki-query`; L2 pages have only their `## Summary` section pre-loaded; L4 pages are skipped unless explicitly named
- L1 pages should collectively stay ≤5k tokens; L2 ≤20k tokens; L3 and L4 have no combined budget constraint
- The `/wiki-lint` tool's `cache_tier_consistency` rule catches wasted preloads (L1 with 0 inbound links), archived-but-hot misconfigurations (L4 with ≥3 inbound links), tier/status mismatches, invalid tier values, and L1 budget overruns
- Six demo pages already carry explicit cache tiers as of v1.1.0-rc8, exercising the consistency lint in production conditions

## Key Quotes

> "Cache tiers make that explicit without changing anything for pages that don't opt in."
— Emphasizes the backward-compatibility guarantee: zero behavior change for unmarked pages.

> "L1 pages trade context tokens for discovery speed. If you promote 50 pages to L1 you've blown 30 k tokens every query."
— Core tradeoff: each L1 page costs query latency and token budget.

> "Default L3 is the right answer for most pages. Only promote a page to L1 or L2 once you've observed `/wiki-query` walking to it repeatedly."
— Advocates data-driven tier assignment over premature optimization.

## Connections

- [[prompt-caching]] — sibling feature at the Anthropic API level; cache-tiers is the application-layer equivalent for controlling context load
- [[reader-shell]] — another opt-in wiki feature; mentioned as a related reference with similar adoption patterns  
- [[llm-wiki]] — the project this feature belongs to; foundational for context management and token budgeting

## Contradictions

None. The design explicitly preserves byte-identical semantics for existing wikis via the L3 default.