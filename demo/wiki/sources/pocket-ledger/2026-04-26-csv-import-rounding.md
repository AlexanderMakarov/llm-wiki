---
title: "Fix cent-rounding drift on imported statements"
type: source
tags: [session, session-transcript, pocket-ledger, claude, float-rounding, integer-minor-units, csv-import, regression-test]
date: 2026-04-26
source_file: raw/sessions/pocket-ledger/2026-04-26T18-43-pocket-ledger-csv-import-rounding.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session identified and fixed a floating-point rounding accumulation bug in pocket-ledger's CSV import, where imported statement totals drifted by several cents due to repeated rounding on each row. The fix switched to integer minor unit (cents) representation internally, rounding only once at the presentation layer. A regression test with a 600-row fixture confirmed the fix eliminated the 4-cent drift observed before the change. No data migration was needed, as stored values are re-parsed from source statements on each import.

## Key Claims

- Repeated float rounding on each row during CSV parsing causes accumulated rounding errors (measured as 4 cents over 600 rows)
- Switching to integer minor unit representation with single rounding at the presentation edge eliminates the drift entirely
- Stored values are re-parsed from source statements on each import, so the fix applies without requiring any migration of already-saved data

## Key Quotes

> "Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge." — identifies the root cause (premature rounding) and the solution pattern

> "Stored values are re-parsed from the original statements on import, so the fix applies on the next run without touching anything already saved." — clarifies that no schema migration or data cleanup is required

## Connections

- [[Python]] — implementation language for the fix
- [[pytest]] — testing framework used for the regression test with fixture
- [[Data Import]] — the context where the rounding bug manifested