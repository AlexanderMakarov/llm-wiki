---
title: "Fix cent-rounding drift on imported statements"
type: source
tags: [session, session-transcript, pocket-ledger, claude, floating-point-arithmetic, rounding-error, csv-import, integer-arithmetic]
date: 2026-05-24
source_file: raw/sessions/pocket-ledger/2026-05-24T18-43-pocket-ledger-csv-import-rounding.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

A financial ledger application's CSV import was accumulating precision loss (~1¢ per 300 rows) due to repeated float rounding on individual amounts. The fix switched the internal representation to integer minor units (cents), deferring rounding to the presentation layer. A regression test using a six-hundred-row fixture confirmed drift of four cents was eliminated after the change.

## Key Claims

- Repeated float rounding during per-row CSV parsing accumulates errors in financial calculations
- Storing monetary amounts as integers (minor units/cents) instead of floats prevents error accumulation
- Rounding should be applied once at the display edge rather than per-operation during import
- No data migration is required; re-parsing existing statements from source files on the next import applies the fix automatically
- A regression test reproduced the four-cent drift over 600 rows and validated its elimination

## Key Quotes

> "Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge."

This articulates the root cause and the solution pattern: deferring rounding to avoid compounding floating-point errors.

> "it was off by four cents over six hundred rows before the change and exact after"

Concrete evidence of the drift and its elimination via the fix.

## Connections

- [[pocket-ledger]] (project) — financial ledger with CSV statement import; float-to-integer conversion eliminated balance drift
- [[Data Import]] (process) — CSV parsing pipeline where accumulated rounding errors originated
  - fact: Minor units stored as integers prevent error accumulation across large imports
- [[Python]] (language) — implementation language for the arithmetic precision fix