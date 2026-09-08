---
title: "UI reference (part 3/6: Graph)"
slug: ui-reference-03
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/ui.md"
content_sha256: 7eb6298d7f4ad87999fa2453589b551356412dea6a6e4d19fc218921bf71850b
---

> Part 3 of 6 of **UI reference** — Graph.

## Graph

URL: `/graph.html`

Interactive force-directed knowledge graph. Details in [`reference/reader-api.md`](reader-api.md) under the graph section.

**What works:**

- Pan / zoom (mouse / trackpad)
- Click a node → focuses its 1-hop neighbourhood; in topic mode it also opens the side panel, in page mode it opens the node's compiled page in a new tab
- Double-click a node → opens its page in a new tab — the [topic page](#topic-pages), or the project page for a topic that routes to one. Double-click is the only gesture that opens a new tab: the side panel's `Open page →`, its session links, and the right-click menu's **Open** all navigate in the current tab like every other link in the site
- Search input in the top-right → highlights matching nodes, dims the rest
- Orphan highlighting — nodes with zero inbound links get a red border
- Cluster toggle — group nodes by kind (the `wiki/` folder behind each topic)
- Stats overlay (bottom-right) — total pages, edges, orphans, avg connections, top-5 hubs
- Dark / light theme mirrors the main site

**Node colours.** One colour per kind, at equal saturation — a topic no wiki page describes is a normal citizen of the map, not a faded placeholder. The legend renders one swatch per kind actually present in the graph, so a vault with no syntheses advertises no synthesis swatch.

| Kind | Colour | |
|---|---|---|
| Sources | violet | `#7c3aed` |
| Entities | blue | `#2563eb` |
| Concepts | green | `#059669` |
| Syntheses | amber | `#d97706` |
| Projects | magenta | `#db2777` |
| Other (no wiki page describes the topic) | lime | `#65a30d` |

Red is deliberately not a kind colour: the map already spends it on two states — the orphan border and a live search match — and a kind sharing it would read as an error.

**Side panel** (topic mode, single click) — topic name, `Sessions`, `Connected topics`, then the same identity facts the topic page carries: `Kind`, `Active`, `Reviewed`. `Kind` always renders, reading `Unclassified topic` when no wiki page describes the node; the two date rows are omitted when the node lacks the field, so a topic with no dates shows the counts and the kind rather than empty rows. `Open page →` follows, then the top connections and the bridging sessions.

**Built-in assets:** every `graph.html` ships with sibling `graph-viewer.js` and `vis-network.min.js` (pinned **9.1.9**, vendored at build time and included in the installed package). The canvas works from the built static site over HTTP, `file://`, or fully offline — no unpkg fetch and no manual host step for vis-network. **Offline fallback:** if either companion script is missing or fails to load, the page shows an inline notice (`#offline-notice`) via script-tag `onerror`, a post-load watchdog when `graph-viewer.js` never runs, and a `typeof vis` check inside the viewer when the library alone is missing — not a blank canvas.

---
