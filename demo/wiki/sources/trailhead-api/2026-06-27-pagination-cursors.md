---
title: "Move list endpoints from offset to cursor pagination"
type: source
tags: [session, session-transcript, trailhead-api, claude, cursor-pagination, offset-pagination, api-list-endpoints, deprecation-headers, stable-sort, pagination-skipping-rows, rest-api-pagination, backward-compatibility]
date: 2026-06-27
source_file: raw/sessions/trailhead-api/2026-06-07T13-26-trailhead-api-pagination-cursors.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session fixed a classic offset pagination bug where new records inserted during a scan would shift the offset and cause subsequent page requests to skip rows. The solution migrated the list endpoint from offset-based to cursor-based pagination, with the cursor encoding both a stable sort column and the primary key as a tiebreak to ensure order stability during concurrent writes. Backward compatibility was preserved by retaining the old offset parameter with a deprecation header; full removal is deferred to a major version bump.

## Key Claims

- Offset-based pagination skips rows when new records are inserted before the current offset during a page scan
- Cursor-based pagination using a stable sort column plus primary key tiebreak eliminates the skipping issue
- Cursors are opaque to clients and encode both sorting values, maintaining order consistency even with concurrent inserts
- The old offset parameter remains functional with a deprecation header rather than immediate removal
- Breaking removal of the old parameter is deferred to a major version bump per versioning policy

## Key Quotes

> "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one." — describes the root cause of row skipping in offset pagination

> "The cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan." — explains how cursor-based pagination solves the stability issue

> "Yes, for now — it still works and returns a deprecation header. Removing it is a breaking change and belongs in a version bump." — justifies the backward compatibility strategy

## Connections

- [[Cursor Pagination]] (concept) — pagination technique using opaque, client-transparent cursors to maintain stable ordering
  - fact: Cursor implementation encodes both a stable sort column and primary key to prevent row skipping when new records are inserted during scanning