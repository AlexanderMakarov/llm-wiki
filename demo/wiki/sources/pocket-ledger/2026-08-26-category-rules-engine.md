---
title: "Add a rules engine for transaction categories"
type: source
tags: [session, session-transcript, pocket-ledger, claude, category-rules, transaction-categorization, first-match-wins, config-driven-matching, amount-threshold]
date: 2026-08-26
source_file: raw/sessions/pocket-ledger/2026-08-26T13-02-pocket-ledger-category-rules-engine.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session replaced pocket-ledger’s hardcoded keyword-based category matching with an ordered, user-defined rules engine loaded from configuration. Each rule pairs a matcher with a category; evaluation is first-match-wins with an explicit fallback for everything else. Matchers can combine description patterns and amount constraints (implicit AND), including thresholds the old if-chain could not express; tests cover an above-threshold-only rule.

## Key Claims

- Transaction categories are assigned by an ordered list of rules from config, not a fixed keyword map or if-chain.
- The first rule whose matcher succeeds sets the category; a dedicated fallback rule handles non-matches.
- Rule ordering is intentional policy; the prior behavior depended on accidental dictionary iteration order.
- A single rule can require both description match and amount conditions (e.g. only above a threshold).

## Key Quotes

> "Category matching is a giant if-chain. I want to define my own rules." — motivation to externalize matching into configurable rules.

> "Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental." — why rule sequence is a first-class design choice.

> "Yes, and the two combine with an implicit and." — description and amount matchers in one rule are conjunctive.

## Connections

- [[pocket-ledger]] (project) — personal ledger app whose transaction categorization was refactored in this session.
  - fact: Category assignment now uses config-backed ordered rules with optional amount predicates.
- [[Configuration]] (concept) — rules and matchers are loaded from user config rather than compiled into code.
  - fact: Matchers and categories are data-driven so users can change behavior without code edits.
