---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 3/3: P · Novel inventions for llmwiki)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, product-roadmap, session-adapter, client-side-search, redaction]
date: 2026-09-07
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-07
---
## Summary

This document synthesizes part 3 of a comprehensive feature audit that maps 161 planned llmwiki features across 16 categories (A–P). It focuses on 15 novel inventions that no prior wiki implementation has, including the session JSONL adapter, command palette, client-side search, syntax highlighting, keyboard shortcuts, and privacy-first redaction. Of the 161 total features, 63 are rated ⭐⭐⭐⭐⭐ (highest priority) and targeted for v0.1 ship.

## Key Claims

- llmwiki will ship **161 total features** across 16 categories; 63 are rated highest-priority (5-star)
- The session JSONL → markdown adapter (P1) is positioned as "the entire reason llmwiki exists"
- **Client-side search with fuzzy matching** (P3) works offline with no dependencies
- **Redaction by default** (P12) for usernames, keys, tokens, and emails is a privacy feature "no other implementation" provides
- **Performance budget** (P13) targets 9-second cold builds and 0.4-second no-op builds, enforced in CI
- **Live-session skip** (P10) for sessions under 60 minutes prevents reading mid-write files
- **Self-demo via GitHub Pages** (P15) on tag push is designed as zero-effort marketing

## Key Quotes

> "The entire reason llmwiki exists" — on the session JSONL adapter (P1)

> "No dependencies, works offline, instant" — rationale for client-side search (P3)

> "No other impl does this" — describing redaction by default (P12)

> "63 features rated ⭐⭐⭐⭐⭐ are what make this a 'god-level' build. They're all ship-in-v0.1 targets." — on the priority tier

## Connections

- [[llmwiki]] (project) — this feature matrix is llmwiki's comprehensive product roadmap and differentiation audit
  - fact: 161 features span 16 categories (A–P), establishing scope for v0.1
  - fact: Session adapter is identified as foundational innovation
  
- [[Adapters]] (concept) — input adapters occupy category B with 11 features
  - fact: Session JSONL adapter (P1) is novel and highest-priority

- [[Static Site]] (product) — categories D (Viewer) and E (Distribution) drive UX and deployment
  - fact: GitHub Pages self-demo on tag push (P15) is a planned feature
  
- [[GitHub Pages]] (platform) — mentioned as deployment target for automated demo site (P15)

- [[Obsidian]] (product) — inspiration for navigation UX (P14: hover-to-preview wikilinks, breadcrumbs)

- [[Wikilinks]] (concept) — P14 adds preview-on-hover, enabling Obsidian-like navigation patterns

- [[Knowledge Graph]] (concept) — wikilink navigation and cross-referencing are core to the feature set

- [[Client-side search]] (new concept) — P3 specifies fuzzy matching with no external dependencies
  - fact: Designed to work offline and provide instant results

- [[Redaction]] (new concept) — P12 defines scope: usernames, API keys, tokens, email addresses
  - fact: Applied by default with no configuration burden

- [[Performance budget]] (new concept) — P13 establishes measurable targets (9s cold, 0.4s no-op) enforced in CI
