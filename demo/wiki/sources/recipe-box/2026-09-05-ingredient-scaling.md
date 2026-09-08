---
title: "Scale ingredient quantities without mangling fractions"
type: source
tags: [session, session-transcript, recipe-box, claude, ingredient-scaling, recipe-fractions, quantity-display, approximate-measures]
date: 2026-09-05
source_file: raw/sessions/recipe-box/2026-09-05T14-03-recipe-box-ingredient-scaling.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session fixed recipe scaling so doubled (or otherwise scaled) amounts stay in exact fractional form during calculation and only convert at display time, snapping to familiar kitchen denominators. Two thirds doubled now shows as one and a third instead of a long decimal. When a scaled amount does not land on a neat common fraction, the UI falls back to the nearest typical measure and labels it approximate, matching how handwritten recipes behave.

## Key Claims

- Scaling arithmetic should preserve exact rationals internally; decimal strings like `0.6666666666666666` cups are a display bug, not the intended stored value.
- Display should prefer mixed numbers and standard denominators (halves, thirds, quarters, etc.) that cooks recognize.
- Values that cannot be represented cleanly as a common fraction should still be shown as the nearest familiar fraction with an explicit approximate indicator.

## Key Quotes

> "Doubling a recipe gives me 0.6666666666666666 cups." — user report that triggered the fraction-first scaling and display work.

> "Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display, snapping to the denominators people actually use in a kitchen." — core design: compute in fractions, render for humans.

> "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway." — policy for non-exact kitchen-friendly amounts.

## Connections

- [[recipe-box]] (project) — ingredient scaling on branch `feat/scaling`; session cwd and project slug match this app.
  - fact: Scaling was changed so doubled thirds display as one and a third, not repeating decimals.
- [[Validation]] (concept) — implied by handling edge cases where scaled quantities do not divide into standard fractions.
  - fact: Non-nice divisions use nearest common fraction plus an approximate flag rather than raw decimals.
