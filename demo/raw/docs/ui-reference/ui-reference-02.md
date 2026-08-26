---
title: "UI reference (part 2/5: Projects index)"
slug: ui-reference-02
project: ui-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/ui.md"
content_sha256: 091e560125d91e049c14221fb0d035f09dac5d63e4986142a6252af727a37d58
---

> Part 2 of 5 of **UI reference** — Projects index.

## Projects index

URL: `/projects/index.html`

Grid view of every project. Each card shows:

- Project name + slug
- Session count (main + sub-agent)
- Token total for the project
- Freshness badge (days since last session)
- Topic chips (from frontmatter `topics: []`)
- Agent badges (Claude / Codex / Copilot / Cursor / Gemini)

Clicking a card navigates to `/projects/<slug>.html` — the project detail page.

### Project detail (`/projects/<slug>.html`)

- Hero — display name plus a `Project` kind chip, `slug`, `created`, `updated`, main-session and sub-agent counts. The chip is the same one a [topic page](#topic-pages) carries, shown here because a project topic routes to this page instead, so the reader sees the kind either way. The two dates are the earliest and latest `date` across the project's own sessions, recomputed every build: project stubs carry no date of their own, so nothing is hand-maintained, and a project whose sessions all lack a date shows neither.
- Project summary (auto-synthesised from sessions)
- **Connected topics** — the topics this project co-occurs with, immediately above the session tables. Same list shape as on a [topic page](#topic-pages) (topic name · shared-session count), and each entry routes exactly as it does everywhere else: `../topics/<slug>.html` normally, `../projects/<slug>.html` for a neighbour that is itself a project. The whole section is omitted — heading included — when the project's topic node has no connections, or when the vault has too few topics for the topic graph to be used at all.
- Sorted session table (date desc)
- Per-project activity heatmap
- Linked entities + concepts that appear across sessions
- Tool-call distribution bar chart

---

## Sessions index

URL: `/sessions/index.html`

Sortable table across every project. Default sort: date desc.

**Columns:** Session · Agent · Project · Date · Cwd · Model · Msgs · Tools.

**Filter bar at top:** Project · Agent · Model · date range · slug substring (Clear resets; selections persist in `sessionStorage` for the tab).

**Activity timeline** above the filter bar — SVG sparkline of sessions/day across the calendar span. Hover, focus, or click a bar to show that day's date and count in the label (native tooltip too).

Clicking a row navigates to `/sessions/<project>/<slug>.html`.

### Session detail (`/sessions/<project>/<slug>.html`)

- **Frontmatter block** — model, date, token counts, tool-call summary
- **Summary** — auto-synthesised 2–4 sentence abstract
- **Key claims** — bullet list
- **Key quotes** — blockquote pulls
- **Conversation** — full transcript, tool outputs collapsible (auto- expand on long blocks)
- **Connections** — `[[wikilinks]]` out to entities, concepts, related sessions
- **Related** — top-3 similarity matches (from heading/body n-gram)
- **Download .md** — nested `sources/<project>/<stem>.md` for AI-agent consumption

---

## Models

URL: `/models/index.html`

Structured info cards for each AI model (per `llmwiki/schema.py :: ModelProfile`):

- Provider · release date · license
- Context window · max output
- Modalities (text / vision / audio)
- Pricing per 1 M tokens (input, cached_input, cache_write, output)
- Benchmark scores (GPQA Diamond, SWE-bench, MMLU, LiveCodeBench, etc.)

---

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
