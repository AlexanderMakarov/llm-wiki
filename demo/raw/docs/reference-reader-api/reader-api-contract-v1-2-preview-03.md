---
title: "Reader API contract (v1.2+ preview) (part 3/3: Migration path — static → hosted)"
slug: reader-api-contract-v1-2-preview-03
project: reference-reader-api
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/reader-api.md"
content_sha256: 9aa2e65696b5fc9bb0fc237b164f64769ba6f5bcd9c659cf82934d2dfee16876
---

> Part 3 of 3 of **Reader API contract (v1.2+ preview)** — Migration path — static → hosted.

## Migration path — static → hosted

1. **Today:** `llmwiki build` writes HTML, nested `sources/*.md`, and site-level AI exports. External tools read them directly. (Done — #116 is this doc.)
2. **Next:** a separate service could wrap the same files behind `/api/v1/*` paths so a reader SPA can fetch them uniformly. No new data, just routing — llmwiki itself stays a static-file generator.
3. **v1.3+:** If a hosted multi-tenant reader ships, the server reuses the same routes with per-user auth. The content pipeline doesn't change.

At no point does the contract require a rewrite of `llmwiki/build.py` — every endpoint maps to something build.py already emits.

## Related

- `llmwiki/build.py` — produces every file referenced above
- `llmwiki/exporters.py` — `llms.txt` + JSON-LD + site-level AI exports
- `llmwiki/raw_docs_site.py` — `documents-tree.json|.js` for the Raw sidebar
- `docs/reference/cache-tiers.md` — `cache_tier` invariant (#52)
- `docs/maintainers/brand-system.md` — theme tokens returned by `/bootstrap`
- `#116` — this issue
- `#112` — reader-first article shell (one client of this contract)
