---
title: "UI reference (part 6/6: Accessibility)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, wcag-2-1, focus-management, contrast-ratios, motion-preferences]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-06.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

This documentation specifies accessibility standards and implementation details for llmwiki's static site output. The site targets WCAG 2.1 AA compliance with specific requirements for alt attributes, keyboard navigation, focus styling, motion preferences, and color contrast. This is part 6 of a larger UI reference guide covering CLI, slash commands, reader API, and article templates.

## Key Claims

- The website targets WCAG 2.1 AA accessibility standards across all pages
- All images require `alt` attributes for screen reader compatibility
- Every page includes a skip-to-content link that appears on keyboard focus
- Focus rings use the accent color with 2 px outline plus 2 px offset
- The `prefers-reduced-motion` user preference is honored by collapsing all transitions to 0.01 ms
- Muted text achieves ≥ 4.8:1 contrast ratio in light mode and ≥ 6.9:1 in dark mode

## Key Quotes

> "WCAG 2.1 AA targeted across the whole site" — establishes the accessibility compliance baseline for the entire platform

> "`prefers-reduced-motion` honoured (all transitions collapse to 0.01 ms)" — demonstrates technical implementation of motion sensitivity preferences

> "Muted text hits ≥ 4.8:1 contrast in light and ≥ 6.9:1 in dark" — specifies precise secondary text contrast requirements

## Connections

- [[WCAG 2.1]] (standard) — the accessibility standard this UI reference implements; full specification in [`../accessibility.md`](../accessibility.md)
- [[llmwiki]] (project) — this is part 6 of the UI reference documentation for the core project
- [[Static Site]] (component) — the generated static site output must implement these accessibility features in its HTML and CSS output

## Contradictions

None identified.