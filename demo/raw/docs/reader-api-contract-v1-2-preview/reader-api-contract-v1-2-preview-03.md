---
title: "Reader API contract (v1.2+ preview) (part 3/3: Migration path — static → hosted)"
slug: reader-api-contract-v1-2-preview-03
project: reader-api-contract-v1-2-preview
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/reader-api.md"
content_sha256: 9e767bc34dd53ad2f22671b62b6f3c8341138bd87455cac8cd01eefecb8efd42
---

> Part 3 of 3 of **Reader API contract (v1.2+ preview)** — Migration path — static → hosted.

## Migration path — static → hosted

1. **Today:** `llmwiki build` writes HTML, nested `sources/*.md`, and site-level AI exports. External tools read them directly. (Done — #116 is this doc.)
2. **v1.2:** Add a tiny `llmwiki serve --api` flag that wraps the same files behind `/api/v1/*` paths so the reader SPA can fetch them uniformly in dev. No new data, just routing.
3. **v1.3+:** If a hosted multi-tenant reader ships, the server reuses the same routes with per-user auth. The content pipeline doesn't change.

At no point does the contract require a rewrite of `llmwiki/build.py` — every endpoint maps to something build.py already emits.

## Related

- `llmwiki/build.py` — produces every file referenced above
- `llmwiki/exporters.py` — `llms.txt` + JSON-LD + site-level AI exports
- `llmwiki/raw_docs_site.py` — `documents-tree.json|.js` for the Raw sidebar
- `docs/reference/cache-tiers.md` — `cache_tier` invariant (#52)
- `docs/design/brand-system.md` — theme tokens returned by `/bootstrap`
- `#116` — this issue
- `#112` — reader-first article shell (one client of this contract)
