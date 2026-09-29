---
title: "UI reference (part 3/8: Graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, knowledge-graph, force-directed-graph, offline-fallback]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-28
---
## Summary

The Graph component (`/graph.html`) is an interactive force-directed visualization of the knowledge base's topics and connections. It supports pan, zoom, click (1-hop focus), search highlighting, and a cluster toggle, with nodes colored semantically by kind and orphans marked with red borders. All JavaScript dependencies are vendored at build time, enabling fully offline operation without external fetches.

## Key Claims

- The knowledge graph uses a force-directed layout rendering all topics as nodes with semantic coloring by kind: Sources (violet), Entities (blue), Concepts (green), Syntheses (amber), Projects (magenta), and Unclassified (lime)
- Single-click on a node focuses its 1-hop neighbourhood; in topic mode it opens the side panel, in page mode it opens the page in the current tab
- Double-click is the only gesture that opens a new tab; all other navigation (side panel links, session links, right-click menu) navigate within the current tab
- Red is reserved for two interactive states—orphan borders (nodes with zero inbound links) and search match highlighting—and deliberately not used as a kind colour to avoid semantic confusion
- The graph includes a cluster toggle to group nodes by kind, a stats overlay (total pages, edges, orphans, average connections, top-5 hubs), and dark/light theme mirroring the main site
- All assets (vis-network v9.1.9 and graph-viewer.js) are vendored at build time; the graph works offline over HTTP, `file://`, or fully disconnected without external fetches
- Offline fallback handling includes inline notices, post-load watchdog detection, and a `typeof vis` check to gracefully degrade if scripts fail to load

## Key Quotes

> "One colour per kind, at equal saturation — a topic no wiki page describes is a normal citizen of the map, not a faded placeholder."

This design principle treats unclassified topics as first-class participants rather than disabled or secondary states.

> "Red is deliberately not a kind colour: the map already spends it on two states — the orphan border and a live search match — and a kind sharing it would read as an error."

Explains the semantic constraint on the colour palette and the intentional reservation of red for interactive state rather than topic classification.

> "The canvas works from the built static site over HTTP, `file://`, or fully offline — no unpkg fetch and no manual host step for vis-network."

Emphasizes the self-contained, offline-first design achieved through bundling dependencies at build time.

## Connections

- [[llmwiki]] (entity) — the knowledge base system whose UI is documented
  - fact: The Graph is a core interactive component of the LLM Wiki static site.

- [[Knowledge Graph]] (concept) — the underlying data structure being visualized
  - fact: The force-directed layout renders topics and their interconnections as an interactive map.

- [[Static Site]] (entity) — the deployment platform for this component
  - fact: The graph is served as a generated asset at `/graph.html` in the built static output.

- [[Wikilinks]] (concept) — the connections visualized as edges
  - fact: Cross-references between topics appear as edges in the graph layout, enabling topic navigation.

## Contradictions

None identified. This is reference documentation without claims that contradict existing wiki entries.