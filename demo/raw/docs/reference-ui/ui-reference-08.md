---
title: "UI reference (part 8/8: Search index + chunks)"
slug: ui-reference-08
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/ui.md"
content_sha256: 7656740cdc53f26b667601ea5fc167c1f813f61908c1f46377e210d82e1e05bf
---

> Part 8 of 8 of **UI reference** — Search index + chunks.

## Search index + chunks

Two levels:

- `site/search-index.json` — ~7 KB meta index (projects, static pages, documents, docs, slash commands, **topics**) + chunk manifest + facet counts + mode badge.
- `site/search-chunks/<project>.json` — per-project session entries with `title`, `url`, `type`, `project`, `date`, `model`, `body`, `heading_max_depth`, `heading_count_by_depth`.
- `site/search-wiki-corpus.json` — the wiki corpus the palette's **Wiki** group searches (#248): every readable `.md` under `wiki/` except `archive/`, `_context.md` included because `wiki_search` scans it too and the two must not diverge. Files are visited in path order through the same safe reader as assistant search: symlinks cannot escape the wiki root, pages over 4 MiB are skipped, and the walk has a 50 MiB aggregate budget. Each retained entry is `{path, title, url, kind, text}` — `path` vault-relative as the assistant reports it, `kind` the lowercased frontmatter `type`, `text` the complete retained page (never a partial read), and `url` the reader page or `null` where the site has none.

Topic entries (`type: "topic"`) point at `topics/<slug>.html` — or at `projects/<slug>.html` for a topic that [routes to a project page](#project-topics-route-to-the-project-page); their `body` includes session count plus `also: …` aliases so a query using any non-canonical spelling still hits the right page, and their `kind` carries the human-readable singular label the palette badge shows (`Entity`, `Concept`, `Project`, … or `Unclassified topic`). `kind` is present on topic entries only. The same payloads ship as `.js` sidecars for `file://` (#20).

The wiki corpus is lazy — it is fetched on first `⌘K`, never on a page view — and `search-index.json` points at it through the **optional** `_wiki_corpus` manifest key. `_wiki_corpus_status` records whether the 50 MiB budget was reached and how many over-4-MiB pages were skipped; the palette shows that incompleteness instead of claiming a missing term occurs nowhere. Optional because a site built before #248 carries no such key: the viewer then reports the gap on the page and renders the Wiki group as broken rather than as silently empty, and it does the same when the payload itself fails to load.

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

Site-wide CSS lives in `llmwiki/render/css.py`. All tokens inherit from the brand system — see [`../maintainers/brand-system.md`](../maintainers/brand-system.md).

Theme toggle (top-right): `light` / `dark`, persists via `localStorage.theme`. System preference (`prefers-color-scheme`) is honoured when no override is set.

---

## Accessibility

WCAG 2.1 AA targeted across the whole site. Specifics in [`../accessibility.md`](../accessibility.md). Notable:

- Every image has an `alt` attribute
- Skip-to-content link appears on every page on keyboard focus
- Focus ring uses the accent colour with 2 px outline + 2 px offset
- `prefers-reduced-motion` honoured (all transitions collapse to 0.01 ms)
- Muted text hits ≥ 4.8:1 contrast in light and ≥ 6.9:1 in dark

---

## Related

- **[CLI reference](cli.md)** — every `python3 -m llmwiki …` subcommand.
- **[Slash commands reference](slash-commands.md)** — the `/wiki-*` surface.
- **[Reader API contract](reader-api.md)** — stable shape of every file the build writes.
- **[Reader-first article shell](reader-shell.md)** — opt-in Wikipedia-style layout for individual pages.
