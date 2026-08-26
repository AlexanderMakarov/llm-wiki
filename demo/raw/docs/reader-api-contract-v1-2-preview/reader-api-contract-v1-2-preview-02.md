---
title: "Reader API contract (v1.2+ preview) (part 2/3: Future endpoint contract)"
slug: reader-api-contract-v1-2-preview-02
project: reader-api-contract-v1-2-preview
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/reader-api.md"
content_sha256: 9e767bc34dd53ad2f22671b62b6f3c8341138bd87455cac8cd01eefecb8efd42
---

> Part 2 of 3 of **Reader API contract (v1.2+ preview)** — Future endpoint contract.

## Future endpoint contract

Every endpoint below maps 1:1 to a file that `llmwiki build` already
produces. The server is a thin JSON wrapper; the content model is what's
already on disk.

Base URL: `<root>/api/v1` (TBD — static deploy keeps `/api/v1/*.json` as
files).

### `GET /api/v1/bootstrap`

One-shot payload the reader fetches on first load so it doesn't have to
chain three requests before showing anything.

```json
{
  "version": "1.1.0rc2",
  "generated_at": "2026-04-19T08:34:42Z",
  "stats": {
    "sessions": 647,
    "projects": 30,
    "entities": 2,
    "concepts": 0,
    "total_bytes": 62691698
  },
  "nav": [
    { "id": "home",          "label": "Home",      "href": "/" },
    { "id": "recent",        "label": "Recent",    "href": "/recent.html" },
    { "id": "graph",         "label": "Graph",     "href": "/graph.html" },
    { "id": "projects",      "label": "Projects",  "href": "/projects/" },
    { "id": "sessions",      "label": "Sessions",  "href": "/sessions/" },
    { "id": "analytics",     "label": "Analytics", "href": "/analytics.html" },
    { "id": "models",        "label": "Models",    "href": "/models/" }
  ],
  "theme": {
    "accent":  "#7C3AED",
    "default": "dark"
  },
  "search": {
    "mode":   "flat",
    "chunks": "/search-chunks/",
    "index":  "/search-index.json"
  },
  "cache_tiers": ["L1", "L2", "L3", "L4"]
}
```

**Client contract.** Safe to cache for 5 minutes. Never returns partial
data — if the site rebuilds mid-request, the server serves the previous
full payload until the new one is ready.

### `GET /api/v1/article?path=<url>`

The article shell already rendered as structured data — lets a SPA skip
HTML parsing entirely.

```json
{
  "url":   "sessions/llm-wiki/2026-04-17T10-12-llm-wiki-refactor.html",
  "slug":  "2026-04-17T10-12-llm-wiki-refactor",
  "title": "LLM Wiki refactor",
  "type":  "source",
  "project": "llm-wiki",
  "model": "claude-sonnet-4-6",
  "date": "2026-04-17",
  "last_updated": "2026-04-17",
  "confidence": 0.75,
  "lifecycle": "reviewed",
  "cache_tier": "L3",
  "tags": ["claude-code", "refactor"],
  "breadcrumbs": [
    { "label": "Home",     "href": "/" },
    { "label": "Projects", "href": "/projects/" },
    { "label": "llm-wiki", "href": "/projects/llm-wiki.html" },
    { "label": "LLM Wiki refactor" }
  ],
  "body_html": "<article>…</article>",
  "body_text": "Raw markdown body without frontmatter, suitable for LLM context.",
  "wikilinks_out": ["Obsidian", "Karpathy"],
  "wikilinks_in":  ["llm-wiki", "AndrejKarpathy"],
  "related": [
    { "slug": "2026-04-16T18-30-llm-wiki-seed", "title": "LLM Wiki seed", "score": 0.82 }
  ],
  "reading_time_minutes": 4,
  "summary": "First-paragraph summary for L2 pre-loading."
}
```

**Required fields:** `url`, `slug`, `title`, `type`, `body_html`,
`body_text`, `wikilinks_out`. Everything else is optional and may be
null/missing.

**Client contract.** The reader MUST gracefully render when optional
fields are missing (a newly ingested page may not have `confidence` or
`cache_tier` yet).

### `GET /api/v1/search?q=<query>&type=<optional>&project=<optional>`

Thin wrapper over the existing client-side index + chunks. Returns the
matches the palette would surface.

```json
{
  "query": "karpathy",
  "mode":  "flat",
  "total": 12,
  "hits": [
    {
      "id":    "session:llm-wiki/2026-04-16T18-30-llm-wiki-seed",
      "url":   "sessions/llm-wiki/2026-04-16T18-30-llm-wiki-seed.html",
      "title": "LLM Wiki seed",
      "type":  "source",
      "project": "llm-wiki",
      "snippet": "Karpathy's pattern spells out what…",
      "score":   0.91,
      "headings": [
        { "depth": 2, "text": "Summary" },
        { "depth": 3, "text": "Karpathy's pattern" }
      ]
    }
  ],
  "facets": {
    "lifecycle":   { },
    "tags":        { },
    "confidence":  { "none": 647 }
  }
}
```

**Mode.** `"flat"` vs `"tree"` — the client-side router today picks the
mode by heuristic (#53 lands the auto-router). The server MUST return
the same mode it used so the client can tell the user in the palette
footer.

**Client contract.** `hits` is capped at 100; the client does its own
pagination. `score` is 0–1 but not calibrated — use for ranking, not
thresholds.

### `POST /api/v1/sync` (internal only)

Trigger a rebuild without waiting for the next watcher tick. Used by
`/wiki-sync` after a successful ingest.

```http
POST /api/v1/sync
Authorization: Bearer <local-token>

{
  "reason": "ingest",
  "pages_changed": ["sources/llm-wiki-refactor.md"]
}
```

Response:
```json
{
  "accepted": true,
  "build_id": "2026-04-19T10:22:01Z",
  "eta_seconds": 2
}
```

**Auth.** Local bearer token only — this endpoint is never exposed to
the public internet. `manifest.json` is the read-side proof that the
build finished (its `generated_at` advances).

---

## Data model invariants

Anything a client can depend on. Cite an invariant by the field it constrains, not by its position — the list renumbers whenever an item is added or removed.

1. **Slugs are stable.** A page's slug is set at ingest and never
   changes on rebuild. Renames produce a new slug and a redirect stub.
2. **Timestamps are UTC ISO-8601 with `Z` suffix.** Never local time.
3. **`cache_tier` is always one of `L1`, `L2`, `L3`, `L4`** (#52).
   Missing = treat as `L3`.
4. **`lifecycle` is always one of** `draft`, `reviewed`, `verified`,
   `stale`, `archived` (#11).
5. **`confidence` is always in `[0, 1]`** or missing. Never percent.
6. **Wikilinks resolve to slugs, not URLs.** `[[Karpathy]]` → `"Karpathy"`
   — the client resolves to a URL via the index.
7. **Frontmatter is authoritative** for metadata. The body is authoritative
   for prose.

## Versioning

- `/api/v1/*` is the long-term contract. Breaking changes bump to `/v2/`
  and keep `/v1/` live for one minor version.
- Additive-only changes (new optional fields, new top-level keys on
  `bootstrap`) don't bump the version.
- Rename of an existing required field **is** a breaking change.

## Content negotiation

Today's static site already does this implicitly:

- `curl .../sessions/<project>/<stem>.html` → HTML
- `curl .../sources/<project>/<stem>.md` → raw session markdown

The future server keeps those paths. `Accept: text/markdown` on a session
HTML route should redirect to the nested `sources/` copy rather than
serving markdown on the HTML URL — that way caches and proxies stay
simple.

---
