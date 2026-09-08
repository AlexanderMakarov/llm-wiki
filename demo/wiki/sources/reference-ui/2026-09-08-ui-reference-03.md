---
title: "UI reference (part 3/6: Graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, knowledge-graph-viewer, vis-network, graph-ui, orphan-highlighting, topic-mode, force-directed-layout, orphan-nodes]
date: 2026-09-08
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the UI reference documents `/graph.html`, the built wiki’s interactive force-directed knowledge graph. It specifies pan/zoom, single-click neighbourhood focus (side panel in topic mode, compiled page in page mode), double-click as the only gesture that opens a node’s page in a new tab, search dimming, orphan highlighting, kind-based clustering, and a stats overlay. Node colours are one saturated swatch per kind present in the vault (including lime for topics with no describing wiki page); red is reserved for orphan borders and search matches, not kinds. The page ships with vendored `graph-viewer.js` and vis-network **9.1.9** so the canvas works over HTTP, `file://`, or offline, with layered offline notices if scripts fail to load.

## Key Claims

- Single-click on a node focuses its 1-hop neighbourhood; in topic mode it opens the side panel, while double-click (and only double-click among graph gestures) opens the topic or routed project page in a new tab.
- Side panel links (`Open page →`, session links, right-click **Open**) navigate in the current tab like the rest of the site.
- The legend shows one swatch per kind actually present; topics without a wiki page use kind lime (`#65a30d`) and side-panel `Kind` reads `Unclassified topic`, with date rows omitted when absent.
- Red is deliberately not assigned to any node kind because it already signals orphan borders and live search matches.
- Every `graph.html` build bundles sibling `graph-viewer.js` and pinned vis-network 9.1.9 with no unpkg fetch; missing or failed loads surface `#offline-notice` via script `onerror`, a post-load watchdog, and a `typeof vis` check in the viewer.

## Key Quotes

> "Double-click is the only gesture that opens a new tab: the side panel's `Open page →`, its session links, and the right-click menu's **Open** all navigate in the current tab like every other link in the site" — defines graph-specific navigation vs site-wide link behaviour.

> "Red is deliberately not a kind colour: the map already spends it on two states — the orphan border and a live search match — and a kind sharing it would read as an error." — colour semantics for kinds vs UI state.

> "The canvas works from the built static site over HTTP, `file://`, or fully offline — no unpkg fetch and no manual host step for vis-network." — offline and packaging guarantee for the graph viewer.

## Connections

- [[llmwiki]] (entity) — the static site that emits `graph.html` and vendored graph assets at build time.
  - fact: Graph behaviour and colours are part of the shipped UI reference for the wiki toolchain.
- [[Static Site]] (concept) — `/graph.html` is a first-class page in the generated site with dark/light theme parity.
  - fact: Built-in `graph-viewer.js` and vis-network are included in the installed package, not loaded from a CDN at runtime.
- [[Knowledge Graph]] (concept) — force-directed visualization of pages/topics, edges, orphans, and hub stats.
  - fact: Cluster toggle groups nodes by the `wiki/` folder kind behind each topic; stats overlay reports pages, edges, orphans, average connections, and top-five hubs.
- [[Wikilinks]] (concept) — graph structure reflects cross-page links; orphan highlighting marks nodes with zero inbound links.
  - fact: Orphan nodes receive a red border in the viewer.
