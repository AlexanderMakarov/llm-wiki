---
title: "UI reference (part 7/8: Command palette (⌘K))"
slug: ui-reference-07
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/ui.md"
content_sha256: 7656740cdc53f26b667601ea5fc167c1f813f61908c1f46377e210d82e1e05bf
---

> Part 7 of 8 of **UI reference** — Command palette (⌘K).

## Command palette (⌘K)

Press `⌘K` (or `Ctrl+K` on Linux/Windows) from any page.

- Results arrive in two groups, **Wiki** first and **Site** second, each with a heading and its result count. Both groups always render: a group with nothing to show keeps its heading and states that it found nothing, so "the wiki has no such page" stays distinguishable from "search is broken" (#248).
- The **Wiki** group runs the same algorithm as `wiki_search` `mode=match` over the same corpus (see [mcp.md](mcp.md)): a literal, case-insensitive substring, no scoring. A page matches by name — its title or its vault-relative path — or by any body line containing the term; name matches come first, then body-only matches, each sorted by path. These semantics replaced the palette's earlier fuzzy scoring for wiki results, so a query of several words that appears nowhere as a literal string returns nothing rather than a best guess; matching what an assistant answers means matching it exactly.
- A Wiki row shows the page's frontmatter `type` as its badge (`wiki` when the page declares none), its title (its path when it has none), the path itself, and its first matching lines with line numbers, folded into `+N more matching lines` past the third. The displayed part of a long matching line starts close enough to the first hit that the highlight cannot sit beyond the row's clipped right edge; the matcher still keeps its full 400-character snippet. A wiki page the site has no reader page for — `wiki/overview.md`, `wiki/log.md`, `candidates/`, `syntheses/`, `categories/` — is still listed with its path and lines but is **not** clickable, and `↑ / ↓` step over it. That is how the group keeps the assistant's full coverage without offering dead ends.
- Every occurrence of the searched term is highlighted in a result's title, its path and its matching lines — in the Site group's rows too — so a row shows at a glance why it matched. Case is folded when matching and the page's own casing is kept in what you read; a term matching in the path but not the body is marked there. Highlighting is presentation only: it never changes which results come back or their order. When a matching wiki summary and a matching raw session or document both open the same reader URL, the Wiki row is shown once and the duplicate Site row is suppressed; the Site row remains available when only the raw content matches.
- Caps are the assistant's: 200 pages and 200 matching lines per text search, after which the group appends a line saying matches were dropped. A capped group routinely reports *fewer* than 200 pages — the line cap trips first, and from then on only a name match can still admit a page. That is the search engine's own behaviour, mirrored deliberately rather than smoothed over.
- The **Site** group is everything the palette indexes that is not a wiki page — static pages, projects, sessions, documents, editorial docs, slash commands, and topic pages (`type: topic`) with their alias spellings (#50) — matched and ordered by the same rule. An empty query browses the head of that index instead of searching; the Wiki group asks for a term instead.
- An empty Site query is only a 10-row browse preview. Any explicit query — text, a structured filter, or `sort:date` — may return up to 200 rows. A filter-only or sort-only query that exceeds that limit says exactly `Showing 200 of N matching results.`; short and common text still obeys the 200-page / 200-line matcher caps.
- The badge on each result reads its `kind` when the entry carries one and its `type` otherwise, so a topic result says `Entity`, `Concept`, `Project` … — or `Unclassified topic` — matching what the map and the topic page call it (#108). The underlying `type` is unchanged.
- Top result on Enter navigates.
- Shows facet chips: `Project`, `Entity type`, `Lifecycle`, `Confidence`, `Tags` — click a facet to filter.
- Footer shows the current mode (`flat` / `tree`) from `search-index.json._mode` and the deep-page ratio (see [`reference/cache-tiers.md`](cache-tiers.md) for the tree-mode heuristic).
- Keyboard: `↑ / ↓` navigate, `Enter` open, `Esc` close.
- Filter by type: `type:topic` / `type:session` / `type:project` / `type:docs` / `type:document` / `type:slash` / `type:page`. `type:topic` still matches every topic result whatever its badge says — the badge reads `kind`, the filter reads `type`.
- The structured filters `type:` / `project:` / `model:` / `date:` / `tags:` / `sort:` narrow the **Site** group only: match mode has no equivalent, so honouring them in the Wiki group would diverge from the assistant. `kind:` is the one filter both groups honour — it is the frontmatter `type`, exactly as `wiki_search`'s own `kind` argument reads it.

---
