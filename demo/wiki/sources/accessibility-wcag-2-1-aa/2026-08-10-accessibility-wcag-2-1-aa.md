---
title: "Accessibility (WCAG 2.1 AA)"
type: source
tags: [wiki-add, raw-doc, session-transcript, accessibility-wcag-2-1-aa, wcag-compliance, accessibility-testing, color-contrast, keyboard-navigation, semantic-html]
date: 2026-08-10
source_file: 
project: accessibility-wcag-2-1-aa
model: 
last_updated: 2026-08-11
---
## Summary

[[llmwiki]] targets WCAG 2.1 Level AA compliance across all generated HTML pages. The project uses [[axe-core]] automated auditing against four representative page types and currently reports zero violations. Coverage includes color contrast validation, keyboard navigation features (skip links, focus indicators, command palette), semantic HTML structure, and reduced-motion support. Several fixes were applied in v0.9 to address contrast ratio issues in muted text and code highlighting.

## Key Claims

- [[llmwiki]] maintains **zero axe-core violations** across home, projects index, sessions index, and session detail page types
- All text tokens meet the WCAG AA minimum contrast ratio of 4.5:1 in both light and dark modes
- The project implements keyboard navigation via skip-to-content link, focus indicators, command palette (`Cmd+K` / `Ctrl+K`), and keyboard shortcuts (`?` for help, `g h`/`g p`/`g s` for navigation, `j`/`k` for table rows)
- Semantic HTML is used consistently: `<html lang="en">`, `<main id="main-content">`, properly labeled `<nav>` elements, and `aria-current="page"` for breadcrumbs
- In v0.9, muted text contrast was increased from 2.56:1 / 4.09:1 to 4.84:1 / 6.97:1, and code keyword highlighting was changed to `#c23a40` to achieve 4.82:1 contrast

## Key Quotes

> "llmwiki targets **WCAG 2.1 Level AA** for all generated HTML pages."

> "Current status: **0 axe-core violations** across all four page types."

— These define the accessibility mandate and current compliance status.

## Connections

- [[axe-core]] — automated accessibility auditing tool integrated into the build pipeline
- [[WCAG 2.1]] — the web accessibility guideline standard being targeted

## Out of Scope (Acknowledged Limitations)

- Screen reader testing (VoiceOver smoke test recommended but not automated)
- WCAG AAA compliance (7:1 contrast ratio for muted text not guaranteed)
- Third-party CDN content (highlight.js theme colors not overridden beyond keywords)