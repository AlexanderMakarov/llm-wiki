---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 3/3: P · Novel inventions for llmwiki)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix-every-feature-across-the-15-prior-implementations, llmwiki-spec, session-adapter, ux-features, privacy-by-default]
date: 2026-08-10
source_file: 
project: feature-matrix-every-feature-across-the-15-prior-implementations
model: 
last_updated: 2026-08-11
---
## Summary

This is part 3 of a comprehensive feature matrix documenting 15 novel inventions for [[LLMWiki]] — capabilities no prior implementation possesses. The session organizes and rates 161 total features across 16 categories (A–P), with 63 identified as five-star "god-level" priorities for v0.1 ship. Distinguishing features include session .jsonl→markdown conversion (the reason [[LLMWiki]] exists), client-side fuzzy search, keyboard shortcuts, and built-in redaction of secrets by default.

## Key Claims

- [[LLMWiki]]'s core value proposition is a **session `.jsonl` → markdown adapter** that no prior implementation offers (P1, rated ⭐⭐⭐⭐⭐)
- Client-side search with built-in fuzzy matching and no external dependencies works offline and instantly (P3, ⭐⭐⭐⭐⭐)
- **Keyboard-driven UX** (forward slash, `g h`, `j/k` navigation) and **Cmd+K command palette** are modern dev-tool standards (P2, P5, both ⭐⭐⭐⭐⭐)
- **Redaction by default** of usernames, API keys, tokens, and emails is novel and no other implementation does this (P12, ⭐⭐⭐⭐⭐)
- Performance budget enforcement in CI (9s cold build, 0.4s no-op) and auto-deploy to GitHub Pages on tag push are structural innovations (P13, P15)
- 63 of 161 features (39%) are rated as five-star ship targets, indicating a highly curated scope

## Key Quotes

> "The entire reason llmwiki exists" — referring to session `.jsonl` → markdown adapter (P1)

> "No other impl does this" — on redaction by default (P12), a privacy-first departure from prior tools

> "63 features rated ⭐⭐⭐⭐⭐ are what make this a 'god-level' build. They're all ship-in-v0.1 targets." — articulating the philosophy behind the feature selection

## Connections

- [[LLMWiki]] — the system being specified; this documents its v0.1 feature scope
- [[Feature specification]] — this is a structured specification of unique selling points vs. prior art (15 implementations compared against)

## Contradictions

- None identified; this is a primary source document defining intended behavior, not a report comparing against implemented reality.