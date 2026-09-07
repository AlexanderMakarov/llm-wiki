---
title: "UI reference (part 5/6: Prototypes hub)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, command-palette, search-index, analytics-page, keyboard-shortcuts, ai-exports]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-05.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

Part 5 of a 6-part UI reference documenting the static-site features of [[llmwiki]]. The session catalogs the prototypes hub (six UX review states before template changes), the recent documents listing, the analytics dashboard (session metrics, cache hit rates, MCP usage, unread source inventory), the command palette (⌘K fuzzy search across all content), the two-level search architecture (meta-index + per-project chunks), AI-consumable export formats (llms.txt, JSON-LD, RSS, sitemap), keyboard shortcuts, and CSS theming with light/dark mode support.

## Key Claims

- The prototypes hub displays six UI states (page shell, article anatomy, drawer browse, search results, empty search, references rail) visually marked with a `#7C3AED` top stripe and "not a live page" metadata to prevent confusion with production pages
- The analytics page aggregates session counts, token usage, cache hit rates, project-by-tokens ranking, MCP call breakdown by tool, and "dead stock" (unread synthesized sources)
- The command palette fuzzy-searches all page titles, bodies, and topic aliases; results are badged by `kind` (Entity, Concept, Project, etc.) and filterable by facets (Project, Entity type, Lifecycle, Confidence, Tags)
- The search system uses a two-level architecture: a ~7 KB meta-index plus per-project chunk files containing session entries with `title`, `url`, `type`, `project`, `date`, `model`, `body`, and heading metadata
- The site exports AI-consumable formats: llms.txt, llms-full.txt (capped 5 MB), graph.jsonld (schema.org), RSS 2.0, sitemap.xml, robots.txt, manifest.json (SHA-256 hashes), and per-session markdown sources
- Keyboard shortcuts enable navigation (⌘K/Ctrl+K for search, `g h/p/s` for home/projects/sessions, `j/k` for table rows, `?` for modal, Esc to close)

## Key Quotes

> "Review-ready UI states for UX iteration **before** larger UI changes touch the live templates." — describing the prototypes hub's role in the design workflow

> "Every prototype carries a **4 px `#7C3AED` top stripe** and a 'Prototype — not a live page' meta block so reviewers never confuse them with real pages." — on visual markers to prevent production confusion

> "The badge on each result reads its `kind` when the entry carries one and its `type` otherwise, so a topic result says `Entity`, `Concept`, `Project` …" — on command palette result badging for topic entries

> "Site-level exports AI agents should start with: `/llms.txt`, `/llms-full.txt`, `/graph.jsonld`, `/sitemap.xml`, `/rss.xml`" — on the entry points for AI-consumable data

## Connections

- [[llmwiki]] (project) — the system whose UI is documented
  - fact: Analytics dashboard tracks session count, token usage (labeled per-session average), cache hit rates, project rankings, and MCP tool usage by sessions vs. documents corpus
  - fact: Command palette searches include `type: topic` entries that route to `topics/<slug>.html` or project pages for topic-routed-to-project cases
  - fact: Recent documents listing collapses chunked docs (`<slug>-01.md` through `<slug>-NN.md`) into a single row with part count
- [[Static Site]] (concept) — the generated HTML/JS output where all these features exist
  - fact: Search index ships as both `site/search-index.json` and `.js` sidecars for `file://` browsing
  - fact: Every session page links to a nested markdown export at `sources/<project>/<stem>.md` for AI agent consumption
- [[Knowledge Graph]] (concept) — graph.jsonld export provides structured entity/concept/source relationships
  - fact: graph.jsonld is listed as a site-level export for AI agents alongside llms.txt, RSS, and sitemap
- [[Observability]] (concept) — the analytics page provides visibility into wiki usage and system performance
  - fact: Analytics dashboard displays session-page reads and doc-page reads (split from `wiki_read_page` hits when telemetry carries signal), MCP telemetry by tool, and dead-stock (unread synthesized sources) as a shared count-badge collapsible listing

## Contradictions

None identified. This is reference documentation describing existing UI.