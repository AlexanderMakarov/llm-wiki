---
title: "Fix cent-rounding drift on imported statements"
type: source
tags: [session, session-transcript, pocket-ledger, claude, accumulation-error, integer-minor-units, float-rounding-error]
date: 2026-05-25
source_file: raw/sessions/pocket-ledger/2026-05-25T18-43-pocket-ledger-csv-import-rounding.md
project: pocket-ledger
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

CSV import was losing precision due to repeated float rounding, with errors accumulating to a few cents per several hundred rows. The fix switched the internal amount representation to integer minor units (pennies as the base unit), deferring rounding to the presentation layer. A regression test with synthetic fixture data reproduced the issue (4-cent drift over 600 rows) and confirmed the fix eliminates accumulation. Existing stored data requires no migration since values are re-parsed from original statements on each import run.

## Key Claims

- Repeated float rounding per imported row accumulated to a 4-cent error over 600 rows.
- Integer minor units (cents as base unit) with single rounding at presentation boundary eliminates accumulation.
- Existing stored data does not require migration; re-parsing from source statements on next import automatically applies the fix.

## Key Quotes

> "Amounts were parsed to floats and rounded per row, so the error accumulated." — Root cause of the financial drift in the import pipeline.

> "Off by four cents over six hundred rows before the change and exact after." — Regression test demonstrating the fix eliminates accumulated error.

## Connections

- [[pocket-ledger]] (project) — Financial tracking application where the CSV import rounding drift occurred and was fixed.
  - fact: Imported statement totals drifted by cents due to repeated float rounding on each row.
  - fact: Solution applies integer minor units with single presentation-layer rounding to prevent accumulation.
