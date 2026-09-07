---
title: "UI reference (part 4/6: Topic pages)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, topic-pages, knowledge-graph, wikilinks]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-04.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

Defines the structure and rendering of topic pages in the [[llmwiki]] UI, establishing how they display facts from two independent sources: sessions (activity dates and reach) and wiki pages (categorization, review date, and editorial content). The design principle is that neither source invents values—sessions provide evidence of citation history, wiki pages provide editorial curation. Topic pages exclude Connections, Sessions, and Sources sections which the system renders separately from the graph.

## Key Claims

- A topic must be mentioned by at least 2 sessions to appear in the graph; vaults yielding fewer than 5 topic nodes fall back to page graph and omit topic pages entirely
- Topics are `[[wikilink]]` targets clustered from sessions, not necessarily backed by wiki pages; an unclassified (non-backed) topic displays an `Unclassified topic` chip
- Topic page identity line format: kind chip · active date range · review date · connected topic count · session count · slug, with each date field omitted entirely if its source is absent, never filled with placeholder
- Session activity dates come exclusively from session `date` frontmatter (oldest to newest, collapsing to one when they agree); wiki page review dates come from `last_updated` frontmatter
- Page content excludes `## Connections`, `## Sessions`, and `## Sources` sections (rendered separately by the graph builder) and empty subsections (innermost first)
- Wikilinks on topic pages resolve contextually: topic names → topic page or project page (depending on backing); session names with compiled pages → session page; unmatched names → plain text (no dead links)
- Project topics (pages under `wiki/projects/`) route to project detail pages rather than topic pages; the rewrite applies uniformly across search, graph UI, and connected topics lists

## Key Quotes

> "sessions supply reach and activity, the topic's own wiki page supplies kind, review date and content. Neither substitutes for the other, and neither is invented."

Formalizes the separation of evidence (sessions) from editorial (wiki pages) as the foundation of the design.

> "Topics are therefore *not* wiki pages: a topic exists because sessions cited the name, and a topic page renders whether or not any page under `wiki/` describes it"

Establishes that a topic's existence depends on citation in sessions, independent of whether backing documentation was written or reviewed.

## Connections

- [[Knowledge Graph]] (concept) — topic pages are the primary browsable surfaces for graph nodes and co-occurrence edges
  - fact: Topics cited by fewer than 2 sessions don't appear in the graph; vaults with <5 nodes fall back to page graph, suppressing all topic pages
- [[Wikilinks]] (concept) — topic pages implement contextual link resolution for cross-topic and cross-session references
  - fact: Wikilink targets name topics, sessions, or documents; unmatched targets degrade to plain text rather than dead links
- [[llmwiki]] (project) — this is part 4 of the official UI reference documentation (6 parts total)