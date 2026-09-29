---
title: "UI reference (part 6/8: Docs hub)"
slug: ui-reference-06
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/ui.md"
content_sha256: 7656740cdc53f26b667601ea5fc167c1f813f61908c1f46377e210d82e1e05bf
---

> Part 6 of 8 of **UI reference** — Docs hub.

## Docs hub

URL: `/docs/index.html`

The editorial entry point — you're reading a page compiled from the same pipeline. Covered in detail by [`tutorials/01-installation.md`](../tutorials/01-installation.md) onward. See also [`style-guide.md`](../style-guide.md).

---

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

Session analytics plus usage-led wiki value (#52) and the candidates review gate (#84). The page opens with a hero line (main sessions · sub-agent runs · projects) and a row of stat cards — tokens (total + per-session average over sessions with token data, labeled e.g. `10.0K / session (4 with token data)`; cumulative billed throughput including cache_read, not context-window occupancy — #223), best cache hit, heaviest project by tokens, and heaviest project by MCP usage.

Below that, sections appear in this order:

1. **Candidates to review** — pending stubs under `wiki/candidates/` (total + by kind) and stale count (default ≥30d). Heading / pending count link to [`/candidates.html`](#candidates). Zero is intentional signal: synthesize-only vaults still show that the review gate exists and is empty.
2. **Activity** — ~18-month GitHub-style heatmaps: **Agents Activity** (session counts), **Wiki MCP calls**, and — when telemetry carries signal — **Session-page reads** and **Doc-page reads** split from `wiki_read_page` hits.
3. **Recent activity** — last entries from `wiki/log.md` (including producer breakdown lines such as `Processed: 2 Claude · 1 Cursor`).
4. **Projects** — filterable card grid (session counts, date range, topic chips) linking to per-project detail pages.
5. **LLM-Wiki MCP usage** — merged value block and MCP table in one section (MCP telemetry only, not `file://` browsing): retrievals · writes · answer rate · payoff-per-page · distinct attributed projects; optional synthesis cost line; sessions vs documents corpus/read mix; top-earning pages; **Dead stock** as a shared count-badge collapsible listing every unread synthesized source (`collapse_section`); per-tool calls, items returned, and zero-hit rate. The live surface is six tools (#196); retired names in historical logs are folded into canonical rows at aggregation time — see [mcp.md](mcp.md).

There is no daily bar chart — trends are read from the heatmaps. Durable counts and series are described in [`reference/state-persistence.md`](state-persistence.md).

---
