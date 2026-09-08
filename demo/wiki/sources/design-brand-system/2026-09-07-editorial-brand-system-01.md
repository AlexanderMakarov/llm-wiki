---
title: "Editorial brand system (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, design-brand-system, css-tokens, wcag-compliance, typography, brand-guidelines]
date: 2026-09-07
source_file: 
project: design-brand-system
model: 
last_updated: 2026-09-07
---
## Summary

This document establishes the canonical visual design system for [[llmwiki]] v1.2.0 (issue #115). It defines [[llmwiki]] as a "reading-first product" and derives all brand decisions from three core purposes: minimizing visual distraction from prose, ensuring consistency across outputs (web, PDF, screenshots, slides), and supporting rendering in light/dark/print/[[Obsidian]] modes. All design tokens (typography, color, elevation, motion) are implemented as CSS custom properties in `llmwiki/render/css.py`, with [[WCAG 2.1]] AA accessibility as a non-negotiable constraint.

## Key Claims

- llmwiki is fundamentally a reading-first product; the brand exists to serve prose, not compete with it.
- Inter and JetBrains Mono are chosen because they have native OS support; web fonts are never shipped to avoid network requests on page render.
- Line-height 1.7 is specified for body copy; denser UI surfaces (nav, tables) use 1.4–1.5.
- All text/background color pairs maintain [[WCAG 2.1]] AA minimum contrast; dark-mode muted text explicitly targets 6.97:1.
- The accent color (#7C3AED, a vibrant purple) is identical in both light and dark modes to maintain product recognizability in screenshots and exports.
- Motion is deliberately minimal—no auto-play, no scroll hijacking, all animations respect `prefers-reduced-motion`.
- All design tokens are centralized as CSS custom properties on `:root` and `[data-theme="dark"]`, not scattered across stylesheets.

## Key Quotes

> "llmwiki is a **reading-first product**. The site is rendered locally from markdown, then handed to the user like a book they wrote." — Defines the foundational design philosophy: the visual system must get out of the way.

> "Never ship web-font files. Inter and JetBrains Mono have first-class system support on all three major OSes or load via the user's browser; we don't want a network request to render a wiki page." — Establishes performance and offline independence as design constraints.

> "llmwiki is a reading surface — motion should be almost invisible. Every timing, duration, and easing choice below is deliberately boring." — Governs motion design: intentional but restrained.

## Connections

- [[llmwiki]] (product) — This is the canonical visual reference for all [[llmwiki]] outputs.
  - fact: All design tokens live in `llmwiki/render/css.py` as CSS custom properties on `:root` and `[data-theme="dark"]`.
  - fact: The system is versioned (v1.2.0) and tracked as issue #115.
- [[Static Site]] (concept) — The design system applies to the published web version and all exports (PDF, screenshots, slides).
  - fact: The design works identically in light mode, dark mode, print, and [[Obsidian]].
- [[WCAG 2.1]] (standard) — Accessibility compliance is a core non-negotiable constraint.
  - fact: Every text/background pair must maintain AA minimum contrast; dark-mode muted text explicitly targets 6.97:1.
