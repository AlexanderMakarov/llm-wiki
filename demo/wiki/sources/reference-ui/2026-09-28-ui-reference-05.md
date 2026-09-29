---
title: "UI reference (part 5/8: Project topics route to the project page)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, project-routing, topic-page-rendering, wikilink-resolution, build-time-rewriting]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-28
---
## Summary

Documents how topic pages render entity and concept content and explains the core routing mechanism: project topics backed by `wiki/projects/` pages route to full project detail pages (`/projects/<slug>.html`) rather than thin topic pages. This routing rewrite is applied once at build time and affects all surfaces—search, map, Connected lists, and wikilinks.

## Key Claims

- Topic pages render entity/concept page content minus `## Connections`, `## Sessions`, and `## Sources` sections (which the topic page generates itself from the graph)
- Section names like `## Key Facts` are not special; any heading structure and introductory prose survive as written
- Empty sections are dropped at render time; a heading with only empty children is pruned
- Wikilinks in content resolve to their actual targets (topic pages, session pages, or topic pages for unmatched names); code spans and fenced blocks preserve example syntax unmodified
- A topic backed by a page under `wiki/projects/` routes to the full project detail page (with heatmap, session cards, charts) rather than a thin topic page
- The project routing rewrite happens once at build time and applies globally: map double-click targets, search index, Connected topics lists, `topics/index.html`, and inline wikilinks
- Project aliases route correctly to the same project detail page
- Routing is skipped when no project page was generated, so the topic gets an ordinary topic page instead (avoiding 404s)

## Key Quotes

> "A topic backed by a page under `wiki/projects/` links to `/projects/<slug>.html` — the full project detail page with its heatmap, session cards and charts — rather than to a thin topic page."

— Explains the core routing design.

> "The rewrite is applied once at build time and every surface honours it: the map's double-click target, the search index entry, Connected topics lists on topic pages and on project pages, `topics/index.html`, and `[[wikilinks]]` cited inside page content."

— Shows the comprehensive scope of the routing system.

## Connections

- [[Static Site]] (entity) — the generated website that applies the routing rewrite at build time
  - fact: Project topics route to project detail pages instead of thin topic pages
  - fact: All surfaces (map, search, Connected lists, wikilinks) honor the rewrite
- [[Wikilinks]] (concept) — cross-references in page content that resolve via the routing system
  - fact: Wikilink targets resolve to wherever the topic resolved, including routed project pages
- [[Knowledge Graph]] (concept) — topic interconnections that respect the project routing
  - fact: Connected topics lists on all pages honor the project routing rewrite
- [[Wiki Synthesis]] (concept) — the build process that applies the rewrite
  - fact: The routing rewrite happens once at build time, not dynamically at runtime