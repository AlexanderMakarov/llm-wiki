---
title: "UI reference (part 3/6: Graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, force-directed-graph, offline-fallback, node-coloring, knowledge-graph-ui]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-03.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

This session documents Part 3 of the UI reference for [[llmwiki]]: the interactive force-directed knowledge graph visualization (`/graph.html`). It specifies interaction patterns (pan/zoom, single-click focus with side panel, double-click to open page, search highlighting), a semantic node-coloring scheme by kind (Sources=violet, Entities=blue, Concepts=green, Syntheses=amber, Projects=magenta, Other=lime), and an offline-first architecture using vendored vis-network 9.1.9 with graceful fallbacks for missing assets.

## Key Claims

- The graph visualization supports pan, zoom, search highlighting, and click-based focus of 1-hop neighborhoods; double-click opens pages in new tabs while all other links navigate in-place.
- Node colors are assigned by semantic kind with equal saturation; a topic without a wiki page is colored normally (lime) rather than visually demoted as a placeholder.
- Red is deliberately reserved for state indication (orphan borders, active search matches) and not assigned to any node kind to avoid visual confusion with error states.
- The implementation vendors vis-network 9.1.9 at build time; graph.html and its companion scripts (`graph-viewer.js`, `vis-network.min.js`) are bundled in the installed package and work fully offline over `file://` with no external CDN fetches.
- Multiple offline fallback layers prevent blank canvas: inline notice on missing script (via `onerror`), post-load watchdog if `graph-viewer.js` never executes, and `typeof vis` check inside the viewer if the library alone fails to load.

## Key Quotes

> "One colour per kind, at equal saturation — a topic no wiki page describes is a normal citizen of the map, not a faded placeholder." — Design principle rejecting visual hierarchies that demote incomplete entries.

> "The canvas works from the built static site over HTTP, `file://`, or fully offline — no unpkg fetch and no manual host step for vis-network." — Core value: offline-first static delivery with zero external runtime dependencies.

> "Offline fallback: if either companion script is missing or fails to load, the page shows an inline notice... not a blank canvas." — Resilience strategy: graceful degradation with visible user feedback.

## Connections

- [[Knowledge Graph]] (concept) — The graph visualization is the primary UI for exploring and understanding relationships between topics in the wiki.
- [[Static Site]] (system) — `graph.html` is a core interactive component of the static site output, deployed via [[GitHub Pages]] or `file://` protocol.
- [[llmwiki]] (project) — This documents the graph UI reference (Part 3 of 6) for the main wiki system.