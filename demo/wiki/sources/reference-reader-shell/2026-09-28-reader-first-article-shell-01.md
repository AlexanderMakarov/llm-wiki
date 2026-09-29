---
title: "Reader-first article shell (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-reader-shell, page-layout, accessibility]
date: 2026-09-28
source_file: 
project: reference-reader-shell
model: 
last_updated: 2026-09-28
---
## Summary

Documents the "reader-first article shell" feature added to llmwiki in v1.2.0 (#112), which wraps session pages in a Wikipedia-style three-column layout (drawer | body | rail) instead of rendering them as transcripts. The implementation includes a slot-based content composition system, responsive CSS grid with three breakpoints, accessibility features (ARIA labels, semantic HTML), and XSS protection, all while remaining fully backward-compatible via an opt-in `reader_shell: true` frontmatter flag. Part 1 covers the scaffolding, opt-in mechanism, and Python API; Part 2 will follow.

## Key Claims

- The reader shell transforms session pages from "logs someone dumped" into "articles someone wrote" using a Wikipedia-inspired layout with drawer navigation, article body, and right-side metadata rail
- The feature is entirely opt-in via `reader_shell: true` frontmatter flag; pages without it render unchanged through the existing pipeline with no selector conflicts
- CSS is fully scoped under `.reader-shell` to prevent style leakage into existing rendering pipelines
- All shell slots (title, subtitle, breadcrumbs, body_html, infobox, drawer_links, revisions, see_also, references, utility_actions) are optional and collapse when empty
- Infobox metadata auto-extracts from nine predefined frontmatter keys: type, project, model, lifecycle, cache_tier, confidence, last_updated, date
- The layout is responsive with three tiers: single-column at ≤760px, two-column body+rail at 761–1100px, three-column full layout at ≥1101px
- XSS safety is ensured by HTML-escaping all dynamic slot content while trusting body_html from the markdown renderer
- Revision tracking and automatic `see_also` extraction from `## Connections` are explicitly out-of-scope for this phase

## Key Quotes

> "The 'reader shell' wraps the same content in a Wikipedia-style encyclopedia layout so pages feel like articles someone wrote, not logs someone dumped."

> "Pages without the flag render through the existing pipeline exactly as before. No existing selectors are redefined; shell CSS is scoped under `.reader-shell` so it can't leak."

> "Every slot is **optional** — empty ones collapse (no empty chrome)."

> "A malicious frontmatter `title: "<script>"` renders as `&lt;script&gt;` — safe."

## Connections

- [[llmwiki]] (entity) — the platform receiving this rendering feature
  - fact: Reader shell is scaffolded in v1.2.0 (#112) as an opt-in feature for session pages
- [[Static Site]] (entity) — where the reader shell layout is deployed
  - fact: Session pages with `reader_shell: true` render using the three-column Wikipedia-style layout instead of transcript format

## Contradictions

None identified. This is new feature documentation with no prior claims in the wiki to contradict.