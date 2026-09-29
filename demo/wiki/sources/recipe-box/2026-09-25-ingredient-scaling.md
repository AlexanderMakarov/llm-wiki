---
title: "Scale ingredient quantities without mangling fractions"
type: source
tags: [session, session-transcript, recipe-box, claude, ingredient-scaling, recipe-fractions, quantity-display, approximate-measures, fraction-arithmetic, recipe-scaling, quantity-conversion, edge-case-handling]
date: 2026-09-25
source_file: raw/sessions/recipe-box/2026-09-05T14-03-recipe-box-ingredient-scaling.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

This session debugged and fixed a recipe-scaling bug in [[recipe-box]] where doubled ingredient quantities displayed as decimal expansions (e.g., `0.6666…` cups) instead of readable kitchen fractions (e.g., 1⅓). The fix preserves exact fractions throughout scaling arithmetic, snapping results to common denominators on display. When exact fractions don't exist, the code falls back to the nearest common fraction and marks it approximate—matching how real recipes handle imprecise conversions. All ingredient_scaling tests pass, including coverage of previously encountered edge cases.

## Key Claims

- Scaled ingredient quantities were displaying as decimal expansions rather than readable fractions.
- Exact fractions are now preserved through scaling arithmetic and snapped to common kitchen denominators (halves, thirds, quarters, etc.) at display time.
- Non-exact scaling falls back to the nearest common kitchen fraction and is marked approximate.
- A retry path in the ingredient handler covers an edge case from prior work.
- Behavior is locked via pytest tests in the ingredient_scaling module.

## Key Quotes

> "Two thirds doubled now reads as one and a third rather than a decimal expansion." — Core fix: quantities render as fractions, not decimals.

> "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway." — Design principle: approximate behavior mirrors real-world recipe practice.

> "The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages." — Commit strategy: include implementation and tests, skip regenerated artifacts.

## Connections

- [[recipe-box]] (entity) — Project providing scalable recipe management with proper quantity handling and display.
  - fact: Ingredient scaling must preserve fractions and avoid decimal expansions to be usable in a recipe interface.
- [[Web App]] (entity) — The user-facing system where scaled recipes and quantities are displayed.
  - fact: Readable fractions are essential for usability; decimal expansions confuse users in a recipe context.
- [[Validation]] (concept) — Testing approach ensuring ingredient scaling works correctly across standard and edge cases.
  - fact: pytest ingredient_scaling tests verify behavior against kitchen-standard fractions and previously discovered edge cases.

## Contradictions

None identified.