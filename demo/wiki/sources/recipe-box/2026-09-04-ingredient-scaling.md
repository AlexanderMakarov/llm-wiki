---
title: "Scale ingredient quantities without mangling fractions"
type: source
tags: [session, session-transcript, recipe-box, claude, fraction-formatting, rational-arithmetic, recipe-scaling, ui-display]
date: 2026-09-04
source_file: raw/sessions/recipe-box/2026-09-04T14-03-recipe-box-ingredient-scaling.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Fixed ingredient scaling in recipe-box to display fractions instead of decimals. The solution keeps quantities as exact fractions through scaling operations and displays results snapped to common kitchen denominators (halves, thirds, quarters), with approximate indicators for non-evenly-divisible values.

## Key Claims

- Doubling a recipe with decimal arithmetic produces unreadable output (e.g., 0.6666666666666666 cups)
- Keeping quantities as exact fractions throughout scaling preserves arithmetic precision better than decimal conversion
- Display formatting can intelligently snap results to kitchen-friendly denominators without precision loss for typical use cases
- Results that don't divide evenly should display as approximate fractions, consistent with how written recipes handle imprecision

## Key Quotes

> "Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display" — Separates precise computation from human-readable presentation

> "Two thirds doubled now reads as one and a third rather than a decimal expansion" — The improved user experience for common scaling operations

> "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway" — Rationale grounded in real-world recipe conventions

## Connections

- [[recipe-box]] (project) — ingredient scaling is core CLI functionality