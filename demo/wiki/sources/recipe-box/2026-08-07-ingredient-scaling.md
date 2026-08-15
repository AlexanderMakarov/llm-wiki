---
title: "Scale ingredient quantities without mangling fractions"
type: source
tags: [session, session-transcript, recipe-box, claude, fraction-arithmetic, recipe-scaling, decimal-to-fraction, quantity-formatting]
date: 2026-08-07
source_file: raw/sessions/recipe-box/2026-08-07T14-03-recipe-box-ingredient-scaling.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session fixed a recipe scaling bug where multiplying ingredients produced unreadable decimal expansions (e.g., 0.666…) instead of familiar kitchen fractions (2/3). The solution stores ingredient quantities as exact fractions during arithmetic, then formats them for display by snapping to common kitchen denominators. Edge cases that don't divide evenly are approximated to the nearest common fraction and marked as approximate.

## Key Claims

- Ingredient quantities should be stored and calculated as exact fractions, not decimals
- The display layer snaps fractions to commonly-used kitchen denominators (halves, thirds, quarters, etc.)
- Doubling 2/3 cup now displays as 1 1/3 instead of approximately 0.667
- Values that don't divide evenly fall back to the nearest common fraction with an "approximate" marker

## Key Quotes

> "Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display, snapping to the denominators people actually use in a kitchen." — Clarifies the architecture: preserve mathematical precision during calculation, format for human readability on output.

> "Two thirds doubled now reads as one and a third rather than a decimal expansion." — Concrete demonstration of the fix working as intended.

> "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway." — Pragmatism: recipes can't express arbitrary precision, so approximation with transparency mirrors real-world practice.

## Connections

- [[recipe-box]] — the project being improved