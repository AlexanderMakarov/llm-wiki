---
title: "Add a rules engine for transaction categories"
type: source
tags: [session, session-transcript, pocket-ledger, claude, rules-engine, rule-ordering, category-matching, config-driven]
date: 2026-08-25
source_file: raw/sessions/pocket-ledger/2026-08-25T13-02-pocket-ledger-category-rules-engine.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Replaced a hardcoded keyword map for transaction categorization with an ordered rule list loaded from configuration. Rules can match on description and amount; the first matching rule determines the category, with an explicit fallback handling unmatched transactions. This makes categorization logic user-customizable and supports amount-based thresholds that were impossible to express in the old code.

## Key Claims

- The original category matching used a hardcoded if-chain/keyword map
- The new design uses an ordered rule list, where rule order determines precedence (first match wins)
- Rules can match on multiple conditions (description AND amount) combined implicitly
- The old code's categorization behavior accidentally depended on dictionary order; the new design makes ordering explicit and intentional
- Amount-based categorization thresholds were impossible to express in the old code but are now supported
- A fallback rule explicitly handles transactions that don't match any other rule

## Key Quotes

> "Category matching is a giant if-chain. I want to define my own rules." — User's motivation for the refactoring

> "Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental." — Critical insight about making rule precedence explicit rather than relying on implementation details

> "Yes, and the two combine with an implicit and." — Clarification that rules can match on both description and amount simultaneously

## Connections

- [[pocket-ledger]] (project) — Personal finance CLI application being enhanced with user-configurable categorization
- [[Rules Engine]] (system) — Ordered rule-matching architecture where first match determines transaction category, supporting multi-field conditions and explicit fallback handling

## Contradictions

None identified.