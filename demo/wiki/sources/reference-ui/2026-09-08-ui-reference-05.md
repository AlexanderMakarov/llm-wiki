---
title: "UI reference (part 5/6: Prototypes hub)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, prototypes-hub, command-palette, analytics-dashboard, search-index-chunks, llms-txt, prototype-pages]
date: 2026-09-08
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the UI reference documents static-site surfaces for UX review and day-to-day navigation: a six-state **Prototypes hub**, **Recent** (with chunked docs collapsed to one row), and **Analytics** (candidates gate, heatmaps, log tail, projects grid, merged MCP value block). It specifies **⌘K/Ctrl+K** command-palette behavior (fuzzy index, facet chips, `type:` filters vs topic **kind** badges), the two-level **search-index.json** + per-project chunk files (including topic entries with aliases), **AI-consumable exports** (`llms.txt`, `graph.jsonld`, `manifest.json`, etc.), global **keyboard shortcuts**, and **light/dark** theming via `localStorage` and brand tokens in `llmwiki/render/css.py`.

## Key Claims

- Prototype pages are explicitly non-live: each has a 4 px `#7C3AED` top stripe and a “Prototype — not a live page” meta block so reviewers do not treat them as production templates.
- On **Analytics**, token stats reflect cumulative billed throughput (including `cache_read`), not context-window occupancy; the UI labels sessions that actually carry token data (e.g. average per session with a count of contributing sessions).
- **Candidates to review** is shown even when the count is zero so synthesize-only vaults still signal that the review gate exists and is empty.
- Command palette result badges display `kind` when present, otherwise `type`; `type:topic` filtering still keys off underlying `type`, so badge text and filter semantics can differ for topic rows.
- Search is split into a ~7 KB meta `site/search-index.json` (facets, mode, topics, chunk manifest) and lazy-loaded `site/search-chunks/<project>.json` bodies; topic entries include alias text in `body` and optional `kind` for palette labeling.
- Live **LLM-Wiki MCP** telemetry on Analytics reflects six current tools; retired tool names in historical logs are folded into canonical rows at aggregation time.
- `llms-full.txt` is a flattened plain-text export capped at 5 MB; `manifest.json` carries SHA-256 hashes per file plus a perf-budget check.

## Key Quotes

> "Review-ready UI states for UX iteration **before** larger UI changes touch the live templates." — rationale for the Prototypes hub

> "Zero is intentional signal: synthesize-only vaults still show that the review gate exists and is empty." — why Analytics always surfaces the candidates section

> "The badge on each result reads its `kind` when the entry carries one and its `type` otherwise" — command palette labeling vs `type:` filters

## Connections

- [[llmwiki]] (entity) — product whose built `site/` pages, search index, exports, and analytics/MCP surfaces are specified here.
  - fact: Session pages expose nested `sources/<project>/<stem>.md` mirrors for agents, aligned with on-page Download .md.
- [[Static Site]] (concept) — HTML routes (`/prototypes/index.html`, `/recent.html`, `/analytics.html`) and shared chrome/theming described in this reference.
  - fact: Site-wide CSS is centralized in `llmwiki/render/css.py` with tokens from the brand system.
- [[Wiki Synthesis]] (concept) — **Candidates to review** and **Dead stock** (unread synthesized sources) tie the analytics UI to harvest/review workflow.
  - fact: Pending stubs under `wiki/candidates/` drive the candidates section and link to `/candidates.html`.
- [[MCP Server]] (concept) — Analytics **LLM-Wiki MCP usage** block reports retrievals, writes, answer rate, per-tool calls, and zero-hit rate from MCP telemetry only (not `file://` browsing).
  - fact: The documented live surface is six tools, with legacy names merged in aggregation.
- [[Wikilinks]] (concept) — Topic search entries and `graph.jsonld` export support cross-page entity/concept/source navigation for humans and agents.
  - fact: `/graph.jsonld` ships a schema.org JSON-LD graph alongside `/llms.txt` and `/ai-readme.md`.
- [[Knowledge Graph]] (concept) — Graph export and topic pages (`topics/<slug>.html`, with project-routed topics) connect palette/search to structured navigation.
  - fact: Topic chunk `body` includes session count and `also: …` alias spellings for non-canonical queries.
