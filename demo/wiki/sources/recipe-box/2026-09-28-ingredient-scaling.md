---
title: "Scale ingredient quantities without mangling fractions"
type: source
tags: [session, session-transcript, recipe-box, claude, ingredient-scaling, recipe-fractions, quantity-display, approximate-measures, fraction-arithmetic, recipe-scaling, quantity-conversion, edge-case-handling, fraction-scaling, test-coverage]
date: 2026-09-28
source_file: raw/sessions/recipe-box/2026-09-05T14-03-recipe-box-ingredient-scaling.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary
The session resolved ingredient-scaling bugs in recipe-box where doubled recipes produced ugly decimals (0.6666...) instead of kitchen-friendly fractions (1⅓). The solution maintains exact fractions through scaling arithmetic and snaps to common denominators for display. Non-exact results fall back to nearest fractions with an "approximate" marker. All tests pass and lint is clean.

## Key Claims
- Quantities are maintained as exact fractions throughout scaling arithmetic, converting only at display time
- Results snap to kitchen-familiar denominators (halves, thirds, quarters, etc.)
- Non-exact divisions fall back to nearest common fractions and are marked approximate
- Edge cases from previous development are covered by retry logic
- All ingredient_scaling tests pass; one unrelated old lint warning remains

## Key Quotes
> "Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display, snapping to the denominators people actually use in a kitchen." — Core design principle for preserving user-friendly fractions during scaling.

> "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway." — Justifies the pragmatic fallback strategy for non-exact results.

## Connections
- [[recipe-box]] (entity) — Application for managing and scaling recipes
  - fact: Ingredient scaling now preserves user-friendly fractions instead of decimal expansions