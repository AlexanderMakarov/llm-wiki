---
title: "Add a rules engine for transaction categories (orbicast)"
type: source
tags: [session, session-transcript, pocket-ledger, claude, category-rules, transaction-categorization, first-match-wins, config-driven-matching, amount-threshold, rules-engine, category-matching, ordered-matching]
date: 2026-09-18
source_file: raw/sessions/pocket-ledger/2026-08-26T13-02-pocket-ledger-category-rules-engine.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary
Replaced pocket-ledger's hardcoded keyword-based transaction categorization with a config-driven rules engine. Rules are applied in declaration order (first match wins) and can match on both description and amount simultaneously; the previous system accidentally depended on dictionary ordering and could not express amount-only conditions. Changes are isolated to interactive sessions and include comprehensive test coverage.

## Key Claims
- The old if-chain for category matching relied on accidental dictionary ordering, making behavior non-deterministic
- A config-driven rules engine with explicit declaration order provides deterministic, user-customizable categorization
- Rules can match on both description and amount fields with implicit AND logic
- Amount-only matching (e.g., above a threshold) was impossible in the old keyword-map system
- The new rules engine does not affect headless or non-interactive execution paths
- Edge cases identified in the previous week are now covered by explicit tests

## Key Quotes
> "Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental."
— Explains the core motivation: the old system's order was non-deterministic

> "There is a test for a rule matching only above a threshold, since that was the case the old code could not express at all."
— Demonstrates increased expressiveness compared to the keyword-map approach

> "No — headless fixtures stay excluded from default synth. This change is interactive-session only."
— Confirms backward compatibility with non-interactive workflows

## Connections
- [[Configuration]] (concept) — the rules engine loads rules from user-defined config files, enabling customization without code changes
  - fact: Rules are applied in declaration order with first-match-wins semantics

## Contradictions
None identified.