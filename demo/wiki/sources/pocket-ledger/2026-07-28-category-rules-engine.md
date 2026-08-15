---
title: "Add a rules engine for transaction categories"
type: source
tags: [session, session-transcript, pocket-ledger, claude, rules-engine, transaction-categorization, first-match-wins, config-driven]
date: 2026-07-28
source_file: raw/sessions/pocket-ledger/2026-07-28T13-02-pocket-ledger-category-rules-engine.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session involved refactoring [[Pocket Ledger]]'s transaction categorization from a hardcoded if-chain into an ordered rules engine loaded from user configuration. Each rule combines matchers on transaction description and amount; the first matching rule determines the category, with an explicit fallback for unmatched transactions. The refactor eliminated reliance on accidental dictionary ordering and enabled new capabilities like amount-based thresholds.

## Key Claims

- Previous category matching depended on dictionary ordering, which was unintentional behavior  
- The new rules engine makes matching order explicit and user-configurable through config files
- Rules combine multiple matchers (description and amount) with implicit AND logic
- Amount-based thresholds on rules were impossible to express in the old hardcoded if-chain

## Key Quotes

> "Category matching is a giant if-chain. I want to define my own rules." — User's motivation for replacing the hardcoded logic

> "Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental." — Reveals how the old system's behavior was inadvertently tied to dict order

## Connections

- [[Pocket Ledger]] — the project where this transaction categorization rules engine was implemented