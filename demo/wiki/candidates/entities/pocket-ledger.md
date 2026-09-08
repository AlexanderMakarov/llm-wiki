---
title: "pocket-ledger"
type: entity
status: candidate
tags: []
sources: [2026-05-25-csv-import-rounding, 2026-05-25-csv-import-rounding, 2026-08-26-category-rules-engine, 2026-08-26-category-rules-engine]
last_updated: 2026-09-08
---

# pocket-ledger

financial ledger with CSV statement import; float-to-integer conversion eliminated balance drift

## Key Facts

- Imported statement totals drifted by cents due to repeated float rounding on each row. [[2026-05-25-csv-import-rounding]]
- Solution applies integer minor units with single presentation-layer rounding to prevent accumulation. [[2026-05-25-csv-import-rounding]]
- Category assignment now uses config-backed ordered rules with optional amount predicates. [[2026-08-26-category-rules-engine]]

## Connections

Named by 4 source page(s), which is the evidence that
justified this candidate:

- [[2026-05-25-csv-import-rounding]]
- [[2026-05-25-csv-import-rounding]]
- [[2026-08-26-category-rules-engine]]
- [[2026-08-26-category-rules-engine]]
