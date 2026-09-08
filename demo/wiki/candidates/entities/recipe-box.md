---
title: "recipe-box"
type: entity
status: candidate
tags: []
sources: [2026-07-31-image-upload-limits, 2026-09-05-ingredient-scaling, 2026-09-05-ingredient-scaling]
last_updated: 2026-09-08
---

# recipe-box

web app where recipe image uploads were hardened on branch `feat/uploads`.

## Key Facts

- Oversized and wrong-type uploads (e.g. video) could be stored before validation; fix targets the upload path for images. [[2026-07-31-image-upload-limits]]
- Type and size limits are applied while reading the upload stream, not after write completes. [[2026-07-31-image-upload-limits]]
- Scaling was changed so doubled thirds display as one and a third, not repeating decimals. [[2026-09-05-ingredient-scaling]]

## Connections

Named by 3 source page(s), which is the evidence that
justified this candidate:

- [[2026-07-31-image-upload-limits]]
- [[2026-09-05-ingredient-scaling]]
- [[2026-09-05-ingredient-scaling]]
