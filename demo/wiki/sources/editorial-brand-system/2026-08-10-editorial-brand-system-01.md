---
title: "Editorial brand system (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, editorial-brand-system, design-system, typography, accessibility, color-palette]
date: 2026-08-10
source_file: 
project: editorial-brand-system
model: 
last_updated: 2026-08-11
---
## Summary

llmwiki's visual design system is canonicalized as a "reading-first" product that prioritizes prose over visual flourishes. The system specifies all design decisions—typography (Inter + JetBrains Mono), light/dark color palettes, elevation/shadow tokens, and motion principles—as CSS custom properties to ensure consistency across static HTML, PDF, print, Obsidian, and social media screenshots. WCAG AA accessibility is mandatory, and system fonts only (no web-font CDN) ensure fast rendering without network dependencies.

## Key Claims

- llmwiki brand serves three purposes: remove visual interference with prose, create unmistakable "llmwiki page" identity across all export formats, and work identically in light/dark/print/Obsidian without setup
- All design tokens live as CSS custom properties in `llmwiki/render/css.py` scoped to `:root` and `[data-theme="dark"]`, enabling the entire palette to flip in one place
- System fonts only—Inter and JetBrains Mono are chosen for native OS support with no web-font files shipped, avoiding CDN requests and ensuring instant rendering
- WCAG 2.1 AA minimum contrast required for every text/background pair; muted text in dark mode is explicitly verified to 6.97:1 ratio
- Accent color (#7C3AED) must be identical in light and dark modes so that exported screenshots and PDFs read as recognizably "llmwiki" even without the full palette
- Motion must be "almost invisible"—maximum four transition durations (0.1s–0.3s), no auto-play animations, no scroll hijacking, mandatory respect for `prefers-reduced-motion`

## Key Quotes

> "The site is rendered locally from markdown, then handed to the user like a book they wrote."
— Frames [[llmwiki]] as a document artifact rather than an interactive tool, justifying the reading-first philosophy throughout.

> "Never ship web-font files."
— Core infrastructure constraint: system fonts + OS fallbacks only, eliminating CDN dependency and enabling instant page rendering.

> "Make every page feel unmistakably like 'an llmwiki page' — so the static site, the PDF export, a screenshot in a tweet, and a slide deck all read as a single product."
— Explains why design tokens must be rigid: visual consistency across radically different output media.

> "Motion should be almost invisible. Heatmaps, graphs, and timelines render once — they don't loop."
— Reading-first products minimize distraction; no auto-play ensures focus stays on content.

## Connections

- [[llmwiki]] — the product whose visual identity and rendering this system authorizes