---
title: "Move list endpoints from offset to cursor pagination"
type: source
tags: [session, session-transcript, trailhead-api, claude, cursor-pagination, offset-pagination, api-list-endpoints, deprecation-headers, stable-sort, pagination-skipping-rows, rest-api-pagination, backward-compatibility, pagination-consistency]
date: 2026-06-30
source_file: raw/sessions/trailhead-api/2026-06-07T13-26-trailhead-api-pagination-cursors.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

The session diagnosed and fixed a classic offset pagination bug where records inserted mid-scan caused subsequent page requests to skip rows. The fix migrated list endpoints to cursor-based pagination, encoding an opaque tuple of stable sort column and primary key. This maintains consistent ordering even with concurrent inserts. Backward compatibility was preserved by keeping the old offset parameter but returning a deprecation header; full removal deferred to a major version bump.

## Key Claims

- Offset pagination with limit/offset parameters skips rows when new records are inserted before the current offset during a scan
- Cursor pagination using (sort_column, primary_key) pairs provides stable ordering across page requests even with concurrent writes
- Cursors are opaque to clients and serve as the durable handle for consistent pagination through results
- The old offset parameter remains functional with a deprecation header for backward compatibility
- Removing the offset parameter entirely would be a breaking change requiring a major version release

## Key Quotes

> "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one." — Root cause of skipped records in offset pagination

> "The cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan." — Core benefit of cursor-based approach

## Connections

- [[Trailhead API]] (entity) — API project where list endpoints were migrated from offset to cursor pagination
  - fact: Previous offset pagination caused skipped records during concurrent inserts
  
- [[Cursor Pagination]] (concept) — Pagination technique using opaque cursors encoding stable sort key plus primary key
  - fact: Prevents skipped rows when records are inserted mid-scan
  - fact: Maintains stable ordering across concurrent writes
  
- [[Offset Pagination]] (concept) — Previous pagination approach vulnerable to skipped rows
  - fact: Skips rows when new records are inserted before the current offset
  - fact: Replaced by cursor pagination in list endpoints

## Contradictions

None identified.