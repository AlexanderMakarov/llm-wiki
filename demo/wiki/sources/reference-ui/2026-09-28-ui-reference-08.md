---
title: "UI reference (part 8/8: Search index + chunks)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, search-index, keyboard-shortcuts, ai-exports, theming, wcag-compliance]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-29
---
## Summary

This reference documentation describes the UI, search functionality, and build outputs of the llm-wiki static site. It covers two-level search indexing with lazy-loaded wiki corpus, AI-consumable exports (llms.txt, graph.jsonld, RSS, sitemap), keyboard shortcuts, theme toggle with system preference support, and WCAG 2.1 AA accessibility compliance.

## Key Claims

- Search index is structured as ~7 KB meta index (`site/search-index.json`) plus per-project chunks (`site/search-chunks/<project>.json`), with optional lazy-loaded wiki corpus (`site/search-wiki-corpus.json`)
- Wiki corpus lazy-loads on first ⌘K with 50 MiB aggregate budget and 4 MiB per-file limits; pages exceeding 4 MiB are skipped and incompleteness is reported to users rather than silently hidden
- Site provides AI-consumable exports at standard URLs: `/llms.txt`, `/llms-full.txt`, `/graph.jsonld`, `/sitemap.xml`, `/rss.xml`, `/robots.txt`, `/ai-readme.md`, and `/manifest.json`
- Eight keyboard shortcuts enable navigation and interaction, including ⌘K (command palette), `/` (search filter), `g h`/`g p`/`g s` (navigation to home/projects/sessions), `j`/`k` (table row traversal), `?` (shortcuts modal), and `Esc` (close)
- WCAG 2.1 AA accessibility is targeted across the whole site with alt text on images, skip-to-content links, 2 px focus rings using accent color, `prefers-reduced-motion` support, and contrast ratios of ≥4.8:1 (light mode) / ≥6.9:1 (dark mode)

## Key Quotes

> "The wiki corpus is lazy — it is fetched on first ⌘K, never on a page view — and `search-index.json` points at it through the **optional** `_wiki_corpus` manifest key."
— Explains the performance optimization for search functionality

> "Site-level exports AI agents should start with: `/llms.txt`, `/llms-full.txt`, `/graph.jsonld`, `/sitemap.xml`, `/rss.xml`, `/robots.txt`, `/ai-readme.md`, `/manifest.json`"
— Defines the AI-consumable export surface for agent discovery and consumption

> "WCAG 2.1 AA targeted across the whole site."
— Establishes the accessibility compliance baseline

## Connections

- [[llmwiki]] (entity) — the system whose UI and build outputs are documented
  - fact: Site implements two-level search indexing with lazy-loaded corpus, AI-consumable exports at standard URLs, keyboard shortcuts for navigation, theme toggle with system preference fallback, and WCAG 2.1 AA accessibility
- [[Static Site]] (concept) — the site architecture and build process
  - fact: Build generates search index structure, per-project chunks, AI-friendly exports (llms.txt, graph.jsonld, RSS, sitemap), keyboard shortcuts, CSS theming system, and accessibility-compliant rendering
- [[WCAG 2.1]] (entity) — accessibility standard the site targets
  - fact: Site implements AA-level compliance with alt text for images, skip-to-content links, focus ring styling (2 px outline + 2 px offset with accent color), reduced-motion support, and high contrast ratios
- [[Reader API]] (concept) — stable contract for build outputs and data structures
  - fact: Defines the shape of search chunks, wiki corpus entries, session exports, and lazy-loaded payloads consumed by the search palette

## Contradictions

None identified.