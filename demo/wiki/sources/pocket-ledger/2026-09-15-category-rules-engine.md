---
title: "Add a rules engine for transaction categories (orbicast)"
type: source
tags: [session, session-transcript, pocket-ledger, claude, category-rules, transaction-categorization, first-match-wins, config-driven-matching, amount-threshold, rules-engine, category-matching, ordered-matching]
date: 2026-09-15
source_file: raw/sessions/pocket-ledger/2026-08-26T13-02-pocket-ledger-category-rules-engine.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Pocket-ledger's transaction categorization was refactored from a hardcoded if-chain to an ordered rule engine loaded from configuration. Each rule specifies description and optional amount matchers (combined with AND); first match wins, with an explicit fallback. This design makes ordering an intentional feature rather than a hidden implementation detail and enables matching patterns (like amount thresholds) that the old code could not express.

## Key Claims

- The previous implementation hardcoded transaction-to-category matching in an if-chain
- The new system loads rules from configuration with explicit ordering; first rule to match determines the category
- Rules can combine description and amount matchers with implicit AND logic
- Ordering is intentional in the new design; the old code accidentally depended on dictionary iteration order
- The new system can express matching patterns (like amount thresholds) that were impossible in the old code
- An edge case from a prior session is handled via a retry path
- Headless fixtures remain excluded from default synthesis; the change affects interactive sessions only
- The test suite validates the rules engine with 10+ passing test cases

## Key Quotes

> "Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental."
— Captures the critical insight: ordering shifts from hidden implementation detail to explicit design decision.

> "A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag."
— Reflects pragmatic documentation: reuse existing references rather than duplicate across docs.

## Connections

- [[Configuration]] (entity) — the refactor moves from hardcoded logic to configuration-driven rules with explicit ordering
  - fact: Each rule is defined in configuration, specifying matchers (description, amount) and the category; first rule to match wins

## Contradictions

None identified.