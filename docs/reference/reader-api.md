# Site file contract (static reader data)

> **What this file is:** the contract for files that `llmwiki build` writes under `site/`. llmwiki ships a **static site only** — open `site/index.html` from disk or serve the `site/` folder with any static file server. There is no llmwiki HTTP API process today.
>
> **Why the filename says “reader-api”:** historical (#116). The doc still freezes shapes so a future thin JSON/SPA wrapper (if we ever add one) does not force a content-model rewrite. Until then, treat every path below as a **file on disk**, not a live endpoint.

## Who should read this

- Maintainers changing `llmwiki/build.py`, `llmwiki/raw_docs_site.py`, or search/tree payloads — so Ctrl+K, Raw Documents, agents, and exports stay aligned.
- Authors of browser extensions, Alfred/Raycast helpers, or agents that read `site/` without scraping HTML.
- Anyone confused by “API” wording: if you only use the built site in a browser, you already consume this contract via HTML + the `.js` sidecars.

## What `llmwiki build` writes today

Paths are relative to the vault’s `site/` root.

| Path | Shape | Purpose |
|---|---|---|
| `/index.html` | HTML | Home |
| `/raw.html` | HTML | Raw Documents shell (Documents sidebar + reader chrome) |
| `/documents/<path>.html` | HTML | Canonical unified reader for one logical document; `…/<slug>-NN.html` stubs redirect to `#part-NN` |
| `/documents-tree.json` | JSON | Shared Documents tree (folder nesting + one leaf per logical document) |
| `/documents-tree.js` | JS | Same tree for `file://` via `window.llmwikiData["documents-tree"]` |
| `/<group>/index.html` | HTML | Project / sessions / models / vs index |
| `/<group>/<slug>.html` | HTML | Individual wiki/session/topic pages |
| `/sources/<project>/<stem>.md` | Markdown | Session / document markdown for download and agents |
| `/llms.txt` | Markdown | Short AI-agent index ([llmstxt.org](https://llmstxt.org)) |
| `/llms-full.txt` | Plain text | Flattened dump (≤ 5 MB) |
| `/graph.jsonld` | JSON-LD | Schema.org entity/concept/source graph |
| `/graph.html` | HTML | Interactive vis-network graph |
| `/search-index.json` | JSON | Top-level search index + facets + chunk manifest |
| `/search-chunks/<project>.json` | JSON | Per-project search chunk (lazy-loaded) |
| `/search-index.js` | JS | Same payload as `search-index.json` → `window.llmwikiData["search-index"]` |
| `/search-chunks/<project>.js` | JS | Same payload as the sibling `.json`, keyed by its manifest path |
| `/manifest.json` | JSON | Every file + SHA-256 + performance budget |
| `/sitemap.xml` | XML | Sitemap with `lastmod` |
| `/rss.xml` | XML | RSS 2.0 of newest sessions |
| `/robots.txt` | Text | AI-friendly; references `llms.txt` |
| `/ai-readme.md` | Markdown | AI-agent navigation instructions |

**`file://` vs a local static server.** Both are supported for browsing. Browsers block `fetch()` of sibling `.json` from `file://`, so interactive pages also load the matching `.js` sidecars. Serving `site/` over `http://127.0.0.1:…` is optional convenience, not a second product surface. UI behaviour for Documents and search: [ui.md](ui.md#raw).

## Logical documents (shared catalog)

Within each folder under `raw/docs/`, files that share a base slug (`runbook.md` or `runbook-01.md` … `runbook-NN.md`) are **one logical document**. Build-time grouping feeds three serializations that must agree on identity:

### `search-index.json` meta entry (`type: "document"`)

| Field | Meaning |
|---|---|
| `id` | Stable id, e.g. `document:<folder>/<base-slug>` or `document:<base-slug>` at vault root |
| `url` | Canonical site-relative unified page (`documents/…/<base-slug>.html`) |
| `title` | Cleaned readable title (no `(part i/N…)` suffix) |
| `type` | Always `"document"` |
| `date` | Latest part date when present |
| `body` | Plain-text sample with budget split across parts, then capped (~1200 chars) so later parts stay findable in Ctrl+K |

### `documents-tree.json` leaf

| Field | Meaning |
|---|---|
| `id` | Same as the search-index `id` |
| `label` | Same as the search-index `title` |
| `href` | Same as the search-index `url` |
| `rel` | First part’s path under `raw/docs/` (sidebar active highlighting) |

Folder nodes carry `name`, nested `folders[]`, and `files[]` (those leaves). The Raw Documents quick filter matches leaf `label`s; it does not invent a third title list.

### Part stubs and provenance

Non-canonical chunk URLs (`documents/…/<base-slug>-NN.html`) are minimal HTML pages (`meta` refresh + `location.replace` + visible fallback link) pointing at the canonical page `#part-NN`. Sibling `.md` copies of each part remain for provenance / download; only the HTML reader is unified.

---

## Future: optional `/api/v1` wrapper (not shipped)

Everything below is a **preview** of how a thin server or SPA might wrap the **same files**. It does not exist in the package today. Do not expect these HTTP routes unless a future release adds them.

Base URL sketch: `<root>/api/v1` (or static deploy of `/api/v1/*.json` as files).

### `GET /api/v1/bootstrap`

One-shot payload for a first load (stats, nav, theme, search mode pointers). Safe to cache briefly; never partial mid-rebuild.

### `GET /api/v1/article?path=<url>`

Structured article shell (`url`, `slug`, `title`, `type`, `body_html`, `body_text`, `wikilinks_out`, optional metadata) so a SPA need not parse HTML.

### `GET /api/v1/search?q=<query>&…`

Thin wrapper over the same client-side index + chunks the palette uses. Cap and ranking rules stay client-aligned.

### `POST /api/v1/sync` (internal only, if ever added)

Trigger a rebuild with a local bearer token — never a public internet surface. Read-side proof of completion remains `manifest.json`’s `generated_at`.

---

## Data model invariants

Cite an invariant by the field it constrains, not by list position — the list renumbers when items change.

1. **Slugs are stable.** Set at ingest; renames produce a new slug and a redirect stub.
2. **Timestamps are UTC ISO-8601 with `Z`.** Never local time.
3. **`cache_tier` is one of `L1`, `L2`, `L3`, `L4`** when present; missing → treat as `L3`.
4. **`lifecycle` is one of** `draft`, `reviewed`, `verified`, `stale`, `archived` when present.
5. **`confidence` is in `[0, 1]`** or missing — never a percent.
6. **Wikilinks resolve to slugs, not URLs.** `[[Karpathy]]` → `"Karpathy"`; the client resolves via the index.
7. **Frontmatter is authoritative** for metadata; the body is authoritative for prose.
8. **Document catalog identity is shared** across search-index `type:document` rows, `documents-tree` leaves, and canonical `/documents/…` URLs (same `id` / title / href).

## Versioning (future HTTP surface only)

- If `/api/v1/*` ever ships, breaking changes bump to `/v2/` and keep `/v1/` for one minor.
- Additive optional fields do not bump the version.
- Renaming a required field is breaking.

## Related

- `llmwiki/build.py` — produces the files above
- `llmwiki/exporters.py` — `llms.txt`, JSON-LD, site-level AI exports
- `llmwiki/raw_docs_site.py` — logical-document grouping, unified + stub HTML, `documents-tree.json|.js`
- [ui.md](ui.md) — human-facing Raw / search behaviour
- [cache-tiers.md](cache-tiers.md) — `cache_tier` meanings
- [`docs/maintainers/brand-system.md`](../maintainers/brand-system.md) — theme tokens a future bootstrap payload might echo
- `#116` — original contract freeze; `#305` — unified document pages
