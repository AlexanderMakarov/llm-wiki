---
title: "UI reference (part 6/6: Accessibility)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, wcag-21-aa, skip-to-content, focus-visible, prefers-reduced-motion, contrast-ratios, wcag-2-1, accessibility, skip-link]
date: 2026-09-08
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-08
---
## Summary

Part 6 of the UI reference locks accessibility expectations for the built wiki: **WCAG 2.1 AA** site-wide, with full detail deferred to `accessibility.md`. It spells out concrete UI rules—`alt` on images, keyboard-revealed skip-to-content, accent-colour focus rings, honouring `prefers-reduced-motion`, and stricter contrast for muted text in light and dark themes—and points readers to CLI, slash commands, reader API, and reader shell docs.

## Key Claims

- The static site is intended to meet **WCAG 2.1 Level AA** on every page, not as an optional theme.
- Every image in the build output must have an `alt` attribute.
- A skip-to-content link is present on every page and becomes visible on **keyboard focus** (not only for mouse users).
- Focus rings use the **accent colour** with a **2 px outline** and **2 px offset**.
- Under `prefers-reduced-motion`, transitions are collapsed to **0.01 ms** so motion is effectively disabled.
- Muted text must reach **≥ 4.8:1** contrast in light mode and **≥ 6.9:1** in dark mode.

## Key Quotes

> "WCAG 2.1 AA targeted across the whole site." — defines the compliance target for the whole static reader experience.

> "`prefers-reduced-motion` honoured (all transitions collapse to 0.01 ms)" — documents the implementation approach for motion sensitivity.

## Connections

- [[WCAG 2.1]] (concept) — AA is the named compliance level; specifics live in the dedicated accessibility doc.
  - fact: Site-wide AA targeting is stated explicitly in the UI reference.
- [[Static Site]] (concept) — these rules apply to HTML/CSS emitted by `llmwiki build`, not to raw or wiki markdown alone.
  - fact: Skip link, focus ring, and contrast rules are described as page-level behaviour.
- [[llmwiki]] (entity) — UI reference is part of the product’s reader and documentation surface.
  - fact: Part 6 closes the six-part UI reference and links to CLI and slash-command docs.
