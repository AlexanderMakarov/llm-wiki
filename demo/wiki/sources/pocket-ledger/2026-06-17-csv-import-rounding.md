---
title: "Fix cent-rounding drift on imported statements (lundric scale map)"
type: source
tags: [session, session-transcript, pocket-ledger, claude, accumulation-error, integer-minor-units, float-rounding-error, csv-import, regression-testing, floating-point-arithmetic, integer-arithmetic]
date: 2026-06-17
source_file: raw/sessions/pocket-ledger/2026-05-25T18-43-pocket-ledger-csv-import-rounding.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

A CSV import feature in pocket-ledger was losing ~1 cent per 600 rows due to repeated float rounding on each imported row. The fix converted internal amount representation from floats to integer minor units (cents) and moved rounding to the presentation layer only. A regression test with a 600-row fixture confirmed the drift (4 cents) before the fix and perfect accuracy afterward.

## Key Claims

- Repeated float-to-float rounding per row in CSV import causes cumulative drift (~4 cents per 600 rows)
- Integer minor-unit representation (storing monetary amounts as integer cents) eliminates cumulative rounding error
- Rounding logic should be applied only once, at the presentation layer, not during data processing
- The fix passed regression testing: 4 tests in 0.2s with a 600-row fixture

## Key Quotes

> "Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge."

This quote encapsulates both the diagnosis (repeated rounding causes drift) and the solution (integer representation with boundary rounding).

## Connections

- [[Pocket Ledger]] (entity) — Financial ledger application with CSV statement import capability
  - fact: Imported CSV amounts were accumulating rounding errors (~4 cents per 600 rows) due to per-row float rounding
- [[Floating-Point Arithmetic]] (concept) — The core technical problem addressed in this fix
  - fact: Switching to integer minor-unit representation and applying rounding only at presentation boundary eliminates cumulative drift
- [[Python]] (entity) — Programming language used for implementation and testing
- [[pytest]] (entity) — Testing framework used for regression validation

## Contradictions

None identified.