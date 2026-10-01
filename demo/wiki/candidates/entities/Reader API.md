---
title: "Reader API"
type: entity
status: candidate
tags: []
sources: [2026-10-01-llmwiki-documentation, 2026-09-28-reader-api-contract-v1-2-preview-02, 2026-09-28-reader-api-contract-v1-2-preview-03, 2026-09-28-ui-reference-08]
last_updated: 2026-10-01
---

# Reader API

the JSON API wrapper being formally specified

## Key Facts

- Four endpoints (bootstrap, article, search, sync) map 1:1 to files produced by `llmwiki build`. [[2026-09-28-reader-api-contract-v1-2-preview-02]]
- Phase 1 (current): external tools read files directly; Phase 2: same files behind API routes; Phase 3: multi-tenant hosting with per-user auth [[2026-09-28-reader-api-contract-v1-2-preview-03]]
- Defines the shape of search chunks, wiki corpus entries, session exports, and lazy-loaded payloads consumed by the search palette [[2026-09-28-ui-reference-08]]

## Connections

Named by 4 source page(s), which is the evidence that
justified this candidate:

- [[2026-10-01-llmwiki-documentation]]
- [[2026-09-28-reader-api-contract-v1-2-preview-02]]
- [[2026-09-28-reader-api-contract-v1-2-preview-03]]
- [[2026-09-28-ui-reference-08]]
