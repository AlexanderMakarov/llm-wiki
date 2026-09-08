---
title: "UI reference (part 4/6: Topic pages)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, topic-pages, wikilink-clustering, static-site-ui, knowledge-graph-thresholds, project-topic-routing, wikilink-resolution]
date: 2026-09-08
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the UI reference defines how **topic pages** (`/topics/<slug>.html` and `/topics/index.html`) are built from clustered `[[wikilink]]` targets in `wiki/sources/*.md`, not from optional entity/concept wiki pages alone. It specifies graph thresholds (minimum sessions per topic and minimum topic count before topic pages exist), the identity line and sections on each topic page, and a strict split between facts from **sessions** (activity, reach, connected topics, session lists) versus facts from a **backing wiki page** (kind chip from folder, `last_updated` as “Reviewed”, body content). It also documents how topic page content is sliced from backing pages, how wikilinks resolve on those pages, and how **project** topics rewrite to full project detail URLs when a compiled project page exists.

## Key Claims

- A topic exists because sessions cited the name (after spelling clustering); it can keep a topic page even when no `wiki/` page backs it or a candidate was never promoted.
- Topics mentioned in fewer than two sessions are dropped from the graph; if the vault has fewer than five topic nodes, the build falls back to the page graph and writes **no** topic pages.
- The kind chip comes only from which `wiki/` folder holds the backing page (`entities/`, `concepts/`, etc.); frontmatter `type` is not used; with no match the chip is always `Unclassified topic`.
- `Active <first> – <last>` and session counts come from session `date` frontmatter and graph evidence; `Reviewed <date>` and page body come only from the backing page’s `last_updated` and markdown body.
- Topic pages render entity/concept body content after the page H1, omitting `## Connections`, `## Sessions`, and `## Sources`, dropping empty sections inside-out, and resolving `[[wikilinks]]` to topic pages, project pages, or session pages as appropriate.
- A topic backed by `wiki/projects/<slug>.md` links to `/projects/<slug>.html` everywhere (graph, search, connected topics, wikilinks in content) when that project page was built; otherwise it stays an ordinary topic page to avoid 404s.

## Key Quotes

> "sessions supply reach and activity, the topic's own wiki page supplies kind, review date and content. Neither substitutes for the other, and neither is invented." — Core data contract for topic page fields.

> "The chip is never dropped: the absence of a backing page is itself a fact" — Why unclassified topics still show a kind chip.

> "The rewrite is skipped when the build wrote no page for that project" — Project routing guard when session-backed project HTML is missing.

## Connections

- [[llmwiki]] (entity) — Product whose static site exposes topic pages as the browsable surface for link targets harvested from sources.
  - fact: Topic pages are generated at `llmwiki build` from graph data and optional backing wiki pages.
- [[Static Site]] (concept) — Topic and docs URLs (`/topics/`, `/docs/index.html`) are part of the compiled HTML site layout described in this reference.
  - fact: Topic index sorts topics by reach (session and link counts per row).
- [[Knowledge Graph]] (concept) — Topics, co-occurrence edges, and session evidence lists are graph-derived; connected topics share at least one session.
  - fact: Connected-topic counts and lists come from co-occurrence, not from hand-written `## Connections` on wiki pages.
- [[Wikilinks]] (concept) — Canonical topic names and aliases come from clustered wikilink spellings in sources; in-page wikilinks on topic pages resolve to topics, projects, or sessions or degrade to plain text.
  - fact: Alternative spellings appear under “Also tagged as” after clustering.
- [[Wiki Synthesis]] (concept) — `wiki/sources/*.md` is the evidence layer that defines which wikilink targets become topics with reach metrics.
  - fact: Reach and activity metrics are tied to which sessions mention each topic.
