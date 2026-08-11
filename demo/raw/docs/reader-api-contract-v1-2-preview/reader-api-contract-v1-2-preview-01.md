---
title: "Reader API contract (v1.2+ preview) (part 1/3)"
slug: reader-api-contract-v1-2-preview-01
project: reader-api-contract-v1-2-preview
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/reader-api.md"
content_sha256: 9e767bc34dd53ad2f22671b62b6f3c8341138bd87455cac8cd01eefecb8efd42
---

> Part 1 of 3 of **Reader API contract (v1.2+ preview)**.

# Reader API contract (v1.2+ preview)

> Status: **contract-only**. No server yet — today the static site is the
> API. This doc locks the shape so when we add a hosted / SPA reader we
> don't have to rewrite the content model. Freezing this now protects
> the build pipeline (`site/` outputs) and the AI-facing markdown under
> `sources/` from drift (#116).

## Why a contract first

llmwiki is, and will stay, **static-site-first**. But a few near-term
bets depend on the data being reachable without HTML parsing:

- A browser extension that answers "what do I know about X" from the
  wiki's `sources/<project>/<stem>.md` next to the current session tab.
- A Raycast/Alfred plugin that hits `manifest.json` + `search-index.json`
  to open a page.
- A future lightweight SPA reader that can live on the same origin as
  the generated site.
- Downstream LLM agents consuming `llms-full.txt` + per-session `.md`
  under `sources/` to answer questions without pulling HTML.

Every one of those wants the same shape of data. This doc says what that
shape is, so refactors of `llmwiki/build.py` can't silently break
clients.

## Shipped today (v1.0+) — read-only, file-based

The static build writes these to `site/` on every `llmwiki build`:

| Path | Shape | Purpose |
|---|---|---|
| `/index.html` | HTML | Home page |
| `/<group>/index.html` | HTML | Project / sessions / models / vs index |
| `/<group>/<slug>.html` | HTML | Individual page |
| `/sources/<project>/<stem>.md` | Markdown | Raw session transcript for download / agents |
| `/documents-tree.json` | JSON | Shared raw-docs file tree (sidebar payload) |
| `/documents-tree.js` | JS | Same tree for `file://` via `window.llmwikiData["documents-tree"]` |
| `/llms.txt` | Markdown | Short AI-agent index ([llmstxt.org spec](https://llmstxt.org)) |
| `/llms-full.txt` | Plain text | Flattened dump (≤ 5 MB) |
| `/graph.jsonld` | JSON-LD | Schema.org entity/concept/source graph |
| `/graph.html` | HTML | Interactive vis-network graph (#118) |
| `/search-index.json` | JSON | Top-level search index + facets + chunk manifest |
| `/search-chunks/<project>.json` | JSON | Per-project search chunk (lazy-loaded) |
| `/search-index.js` | JS | Same payload as `search-index.json`, assigned to `window.llmwikiData["search-index"]` (#20) |
| `/search-chunks/<project>.js` | JS | Same payload as the sibling `.json`, keyed by its manifest path (#20) |
| `/manifest.json` | JSON | Every file + SHA-256 + performance budget |
| `/sitemap.xml` | XML | Standard sitemap with `lastmod` |
| `/rss.xml` | XML | RSS 2.0 feed of newest sessions |
| `/robots.txt` | Text | AI-friendly, references `llms.txt` |
| `/ai-readme.md` | Markdown | AI-agent navigation instructions |

These are already the API. Everything below in this doc describes the
**future hosted/SPA surface** that will be fed by the same data shapes —
no new content pipeline, just new transports.

---
