---
title: "REST API"
type: concept
status: candidate
tags: []
sources: [2026-06-07-pagination-cursors, 2026-06-07-pagination-cursors, 2026-08-11-request-id-logging, 2026-08-11-request-id-logging, 2026-09-06-schema-migration-safety]
last_updated: 2026-09-08
---

# REST API

HTTP API with paginated list endpoints

## Key Facts

- Migrated from offset to cursor-based pagination to prevent row skipping during concurrent data modifications [[2026-06-07-pagination-cursors]]
- List endpoints moved from offset to cursor pagination while still accepting the old parameter. [[2026-06-07-pagination-cursors]]
- Request ID returned as a response header allows clients to correlate failed requests with server logs [[2026-08-11-request-id-logging]]
- Correlation ids are intended for multi-request log traffic on the API surface. [[2026-08-11-request-id-logging]]
- Session subjects tie migration work to the API project’s data layer, not a standalone migration tool repo. [[2026-09-06-schema-migration-safety]]

## Connections

Named by 5 source page(s), which is the evidence that
justified this candidate:

- [[2026-06-07-pagination-cursors]]
- [[2026-06-07-pagination-cursors]]
- [[2026-08-11-request-id-logging]]
- [[2026-08-11-request-id-logging]]
- [[2026-09-06-schema-migration-safety]]
