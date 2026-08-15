---
title: "Editorial brand system (part 2/2: 5. Spacing)"
type: source
tags: [wiki-add, raw-doc, session-transcript, editorial-brand-system, design-tokens, spacing-scale, theming, css-variables]
date: 2026-08-10
source_file: 
project: editorial-brand-system
model: 
last_updated: 2026-08-11
---
## Summary

This document specifies the design token system for the editorial brand: canonical spacing values (2–48 px, currently inlined but scheduled for scale token abstraction), export consistency ensuring all artifacts (HTML, PDF, slides, QMD, Obsidian) inherit tokens from a single source (`llmwiki/render/css.py`), and style guidelines for typography, theming, and component reuse. Critical principle: dynamic theming via global `data-theme` CSS variable, not per-component opt-ins.

## Key Claims

- The canonical spacing scale (2, 4, 8, 12, 16, 24, 32–48 px) is in use across the codebase; future named scale tokens (`--space-1`…`--space-6`) are roadmapped but not yet implemented.
- All generated artifacts (static HTML site, graph viewer, PDF, Marp slides, Quarto exports, Obsidian vault symlinks) must inherit design tokens from a canonical CSS source to maintain visual consistency.
- Color contrast must be implemented via CSS variables, never inline styles, so the `data-theme` toggle can switch the entire palette atomically.
- Only two web fonts are permitted: Inter and JetBrains Mono; mixing fonts within prose or using custom web fonts violates the brand spec.

## Key Quotes

> "Spacing is inlined in rules (padding/gap/margin). The canonical steps used across the codebase: 2 px, 4 px, 8 px, 12 px, 16 px, 24 px, 32–48 px." — defines current spacing authority and constraint on future values.

> "All generated artifacts must inherit the same tokens" — core principle from the export consistency table, ensuring visual uniformity across formats.

> "Don't build contrast into the HTML (e.g. `<span style="color:white">`); always go through a variable so the theme toggle works." — critical pattern for enabling dynamic theming.

> "Flip the whole palette via `data-theme`, not per-component opt-ins." — global state management approach.

## Connections

- [[Design Tokens]] — this document establishes the token naming, spacing scale, color palette, and export rules for the system
- [[Theme Toggle]] — the CSS variable architecture described here enables dynamic palette switching

## Contradictions

None identified.