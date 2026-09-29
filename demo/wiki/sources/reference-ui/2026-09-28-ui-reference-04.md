---
title: "UI reference (part 4/8: Topic pages)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, topic-pages, static-site-generation, information-architecture]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-28
---
## Summary

This page documents the structure, visibility rules, and information sources for topic pages in the [[llmwiki]] static site. It explains how topics are created (either from cited [[wikilinks]] or curated pages), when they are skipped, the three thresholds controlling their visibility, and the distinction between reach data (supplied by sessions) and identity/content data (supplied by wiki pages).

## Key Claims

- A topic exists if it is either a wikilink target cited in `wiki/sources/*.md` or a curated page under `wiki/entities/` or `wiki/concepts/`, independent of whether the other source exists.
- Topics are skipped from the static site when they have both no connected topics in the co-occurrence graph *and* no content left after removing title, Connections, Sessions, and Sources sections.
- Three independent thresholds gate topic visibility: `DEFAULT_MIN_REFS` (configurable per vault, default 3), `min_sessions` (2, non-configurable), and `_TOPIC_GRAPH_MIN_NODES` (5, non-configurable).
- Curated entity and concept pages are exempt from the `min_sessions` threshold and render as graph nodes regardless of how many sessions mention them.
- Topic pages source their reach data (active dates, session counts, connected topics) from session evidence, while kind, review date, and content come only from the backing wiki page.

## Key Quotes

> "A topic is therefore not the same thing as a wiki page in either direction: a derived topic renders whether or not any page under `wiki/` describes it — an un-promoted candidate, or a name a reviewer declined, keeps its page indefinitely — while every curated entity and concept gets one regardless of reach."

> "This is the distinction to keep straight: sessions supply reach and activity, the topic's own wiki page supplies kind, review date and content. Neither substitutes for the other, and neither is invented."

## Connections

- [[llmwiki]] (entity) — the system whose UI and topic architecture is documented here.
  - fact: Topic pages are rendered at `/topics/<slug>.html` as part of the published output.
- [[Static Site]] (entity) — the generated website output that hosts topic pages and the knowledge graph viewer.
  - fact: Topic pages list connected topics, sessions, and page content; they are reachable via `/topics/index.html`, the command palette, and the graph visualization.
- [[Knowledge Graph]] (concept) — the co-occurrence graph that determines topic connectivity.
  - fact: Topics are skipped if they have no edges in the co-occurrence graph and no content of their own; the graph rendering threshold `_TOPIC_GRAPH_MIN_NODES` controls whether `graph.html` shows the topic graph or falls back to the page graph.
- [[Wikilinks]] (concept) — the double-bracket syntax that creates topic candidates.
  - fact: A wikilink target becomes a topic candidate when cited in three or more pages (controlled by `DEFAULT_MIN_REFS`); curated pages become topics regardless of citation.

## Contradictions

None identified.