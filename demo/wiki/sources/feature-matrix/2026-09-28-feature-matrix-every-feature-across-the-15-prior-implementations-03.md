---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 3/3: P · Novel inventions for llmwiki)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, session-adapter, client-side-search, redaction-privacy]
date: 2026-09-28
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-28
---
## Summary

This is part 3 of a three-part feature matrix that catalogs 15 novel features unique to llmwiki—capabilities no prior implementation of session or knowledge management has shipped. The document emphasizes the session `.jsonl` → markdown adapter as llmwiki's foundational contribution, alongside modern UX innovations (command palette, keyboard shortcuts), client-side full-text search, built-in redaction for sensitive data, and performance budgets enforced in CI. Across 16 feature categories, llmwiki targets 161 total features, with 63 rated as "god-level" (⭐⭐⭐⭐⭐) priorities for v0.1.

## Key Claims

- The session adapter (P1) converting `.jsonl` session logs to markdown is "the entire reason llmwiki exists"—the core novel differentiator.
- No prior implementation includes built-in redaction by default for keys, tokens, emails, with optional username redaction (P12).
- llmwiki will ship 161 features across 16 categories, of which 63 are 5-star priority for v0.1 release.
- Client-side search with fuzzy matching (P3) offers offline operation and no external dependencies—a feature distinction from peers.
- Adapter registry with schema version tracking (P11) and performance budgets enforced in CI (P13, 9s cold / 0.4s no-op) reflect systematic extensibility and reliability.

## Key Quotes

> "The entire reason llmwiki exists" — on the session `.jsonl` → markdown adapter (P1), stating it is the foundational feature that motivated the entire project.

> "No other impl does this" — on redaction by default for keys, tokens, emails (P12), emphasizing a unique privacy-first design choice.

## Connections

- [[llmwiki]] (entity) — the subject of the feature roadmap; this matrix defines its planned v0.1 feature set.
  - fact: 161 total features across 16 categories, with 63 rated 5-star priority.
- [[Adapters]] (entity) — the session adapter is the novel core feature, plus the adapter registry (P11) provides extensible ingestion contracts.
  - fact: The session `.jsonl` → markdown adapter is described as the reason llmwiki exists.
- [[Static Site]] (entity) — many novel features are client-side viewer innovations (command palette, client-side search, syntax highlighting, breadcrumbs, hover preview).
  - fact: P3 proposes client-side search index with fuzzy matching for offline operation and zero dependencies.
- [[Wiki Synthesis]] (concept) — adapter registry with schema versioning (P11) enables clean extensibility for ingestion workflows.
  - fact: P11 specifies adapter registry with schema version tracking for formalized ingestion contracts.
- [[GitHub Actions]] (entity) — performance budget enforcement (P13) is built into CI/CD pipeline with concrete targets.
  - fact: P13 enforces a performance budget in CI: 9s cold build, 0.4s no-op builds.
- [[Wikilinks]] (concept) — hover-to-preview wikilinks (P14) is a novel Obsidian-inspired navigation feature.
  - fact: P14 proposes client-side hover previews for wikilinks to improve knowledge graph navigation.

## Contradictions

None identified. This is a forward-looking specification document with no claims contradicting prior session or system design records.