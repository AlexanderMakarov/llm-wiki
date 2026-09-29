---
title: "Fix cent-rounding drift on imported statements (lundric scale map)"
type: source
tags: [session, session-transcript, pocket-ledger, claude, accumulation-error, integer-minor-units, float-rounding-error, csv-import, regression-testing]
date: 2026-06-14
source_file: raw/sessions/pocket-ledger/2026-05-25T18-43-pocket-ledger-csv-import-rounding.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Fixed a floating-point precision bug in [[Pocket Ledger]]'s CSV import where amounts rounded per row caused cumulative error (4 cents drift over 600 rows). Switched internal representation from floats to integer minor units and deferred rounding to the presentation layer only. Validated with a pytest regression test.

## Key Claims

- Float amounts parsed and rounded per row during CSV import caused cumulative precision loss.
- The accumulated rounding error was 4 cents over 600 rows before the fix.
- Using integer minor units internally (cents as integers) eliminates per-row rounding error.
- Rounding should occur only once at the presentation edge, not during each row operation.

## Key Quotes

> "Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge."

— Core insight on the architectural fix.

## Connections

- [[Pocket Ledger]] (entity) — financial transaction tracking application
  - fact: CSV import totals diverged from statements by cents due to float rounding accumulation
- [[Float Rounding]] (concept) — precision loss from repeated rounding operations on floating-point values
  - fact: Rounding each imported row independently caused 4-cent drift over 600 rows
- [[Integer Minor Units]] (concept) — storing monetary amounts as integers (cents) rather than floats to preserve precision through calculations
  - fact: Replacing float representation with integer minor units eliminated the rounding error entirely

## Contradictions

None identified.