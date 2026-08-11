---
title: "UI reference (part 4/5: Prototypes hub)"
slug: ui-reference-04
project: ui-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/ui.md"
content_sha256: 091e560125d91e049c14221fb0d035f09dac5d63e4986142a6252af727a37d58
---

> Part 4 of 5 of **UI reference** — Prototypes hub.

## Prototypes hub

URL: `/prototypes/index.html`

Review-ready UI states for UX iteration **before** larger UI changes touch the live templates. Six states:

| Slug | What's shown |
|---|---|
| `page-shell` | layout skeleton — nav + footer + breadcrumb, empty content slot |
| `article-anatomy` | annotated session page with orange callouts on every slot (frontmatter, summary, transcript, connections, related) |
| `drawer-browse` | faceted project-browse drawer open (by project / lifecycle / cache_tier) |
| `search-results` | command palette mid-query, 10+ results |
| `empty-search` | no-match state with escape-hatch links |
| `references-rail` | article with sticky right-hand `## Connections` rail |

Every prototype carries a **4 px `#7C3AED` top stripe** and a "Prototype — not a live page" meta block so reviewers never confuse them with real pages.

---

## Recent

URL: `/recent.html`

Newest raw documents first, one row per logical document — chunked docs (`<slug>-01.md` … `<slug>-NN.md` in one folder) collapse into a single row with a part count. Each row shows title, date, and origin source, and links into the Home tree browser.

---

## Analytics

URL: `/analytics.html`

Session analytics plus usage-led wiki value (#52) and the candidates review gate (#84). The page opens with a hero line (main sessions · sub-agent runs · projects) and a row of stat cards — tokens (total + per-session average), best cache hit, heaviest project by tokens, and heaviest project by MCP usage.

Below that, sections appear in this order:

1. **Candidates to review** — pending stubs under `wiki/candidates/` (total + by kind) and stale count (default ≥30d). Heading / pending count link to [`/candidates.html`](#candidates). Zero is intentional signal: synthesize-only vaults still show that the review gate exists and is empty.
2. **Activity** — ~18-month GitHub-style heatmaps: **Agents Activity** (session counts), **Wiki MCP calls**, and — when telemetry carries signal — **Session-page reads** and **Doc-page reads** split from `wiki_read_page` hits.
3. **Recent activity** — last entries from `wiki/log.md` (including producer breakdown lines such as `Processed: 2 Claude · 1 Cursor`).
4. **Projects** — filterable card grid (session counts, date range, topic chips) linking to per-project detail pages.
5. **LLM-Wiki MCP usage** — merged value block and MCP table in one section (MCP telemetry only, not `file://` browsing): retrievals · writes · answer rate · payoff-per-page · distinct attributed projects; optional synthesis cost line; sessions vs documents corpus/read mix; top-earning pages; **Dead stock** as a shared count-badge collapsible listing every unread synthesized source (`collapse_section`); per-tool calls, items returned, and zero-hit rate.

There is no daily bar chart — trends are read from the heatmaps. Durable counts and series are described in [`reference/state-persistence.md`](state-persistence.md).

---

## Command palette (⌘K)

Press `⌘K` (or `Ctrl+K` on Linux/Windows) from any page.

- Fuzzy match over **every** page title + body — including topic pages (`type: topic`) and their alias spellings (#50).
- The badge on each result reads its `kind` when the entry carries one and its `type` otherwise, so a topic result says `Entity`, `Concept`, `Project` … — or `Unclassified topic` — matching what the map and the topic page call it (#108). The underlying `type` is unchanged.
- Top result on Enter navigates.
- Shows facet chips: `Project`, `Entity type`, `Lifecycle`, `Confidence`, `Tags` — click a facet to filter.
- Footer shows the current mode (`flat` / `tree`) from `search-index.json._mode` and the deep-page ratio (see [`reference/cache-tiers.md`](cache-tiers.md) for the tree-mode heuristic).
- Keyboard: `↑ / ↓` navigate, `Enter` open, `Esc` close.
- Filter by type: `type:topic` / `type:session` / `type:project` / `type:docs` / `type:document` / `type:slash` / `type:page`. `type:topic` still matches every topic result whatever its badge says — the badge reads `kind`, the filter reads `type`.

---

## Search index + chunks

Two levels:

- `site/search-index.json` — ~7 KB meta index (projects, static pages, documents, docs, slash commands, **topics**) + chunk manifest + facet counts + mode badge.
- `site/search-chunks/<project>.json` — per-project session entries with `title`, `url`, `type`, `project`, `date`, `model`, `body`, `heading_max_depth`, `heading_count_by_depth`.

Topic entries (`type: "topic"`) point at `topics/<slug>.html` — or at `projects/<slug>.html` for a topic that [routes to a project page](#project-topics-route-to-the-project-page); their `body` includes session count plus `also: …` aliases so a query using any non-canonical spelling still hits the right page, and their `kind` carries the human-readable singular label the palette badge shows (`Entity`, `Concept`, `Project`, … or `Unclassified topic`). `kind` is present on topic entries only. The same payloads ship as `.js` sidecars for `file://` (#20).

The palette lazy-loads chunks as the query narrows. See [`reference/reader-api.md`](reader-api.md) for the stable shape.

---

## AI-consumable exports

Every session page links to a nested markdown copy for agents:

- `sources/<project>/<stem>.md` — raw session markdown (same as the page Download .md button)

Site-level exports AI agents should start with:

| URL | Purpose |
|---|---|
| `/llms.txt` | short index per [llmstxt.org](https://llmstxt.org) |
| `/llms-full.txt` | flattened plain-text dump (capped at 5 MB) |
| `/graph.jsonld` | schema.org JSON-LD entity / concept / source graph |
| `/sitemap.xml` | standard sitemap with `lastmod` |
| `/rss.xml` | RSS 2.0 of newest sessions |
| `/robots.txt` | AI-friendly robots + link to `llms.txt` |
| `/ai-readme.md` | navigation instructions aimed at AI agents |
| `/manifest.json` | SHA-256 hashes for every file + perf-budget check |

---

## Keyboard shortcuts

Press `?` on any page to see the shortcuts modal. Current set:

| Key | Does |
|---|---|
| `⌘K` / `Ctrl+K` | open command palette |
| `/` | focus search filter (on index pages) |
| `g h` | go to home |
| `g p` | go to projects |
| `g s` | go to sessions |
| `j` / `k` | next / previous row (on table views) |
| `?` | show this shortcut modal |
| `Esc` | close modal / palette |

---

## Theming

Site-wide CSS lives in `llmwiki/render/css.py`. All tokens inherit from the brand system — see [`../design/brand-system.md`](../design/brand-system.md).

Theme toggle (top-right): `light` / `dark`, persists via `localStorage.theme`. System preference (`prefers-color-scheme`) is honoured when no override is set.

---
