---
title: "Move list endpoints from offset to cursor pagination"
type: source
tags: [session, session-transcript, trailhead-api, claude, cursor-pagination, offset-pagination, api-list-endpoints, deprecation-headers, stable-sort]
date: 2026-06-07
source_file: raw/sessions/trailhead-api/2026-06-07T13-26-trailhead-api-pagination-cursors.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session fixed missing rows on trailhead-api list endpoints by replacing offset paging with cursor paging. Offset scans shift when rows are inserted mid-request, so clients skip records; cursors use a stable sort column plus primary key as a tiebreak in an opaque token so order stays consistent. The legacy offset parameter remains supported for now and returns a deprecation header; removing it is deferred to a breaking version bump.

## Key Claims

- Offset pagination on list endpoints can skip rows when new records are inserted before the current offset during a multi-page scan.
- Cursor pagination keys on a stable sort column and primary key (tiebreak), encoded in an opaque client-facing cursor.
- The previous offset query parameter is still accepted and triggers a deprecation response header until a major version removes it.

## Key Quotes

> "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one." — rationale for abandoning offset paging on live lists

> "Removing it is a breaking change and belongs in a version bump." — why offset remains temporarily with deprecation only

## Connections

- [[REST API]] (concept) — list endpoint paging behavior and backward-compatible deprecation headers
  - fact: List endpoints moved from offset to cursor pagination while still accepting the old parameter.
- [[SQLite]] (entity) — backing store implied for ordered list scans and cursor key columns
  - fact: Pagination design assumes stable ordering over stored rows during concurrent inserts.
- [[trailhead-api]] (project) — API codebase where `feat/pagination` implemented cursor-based list paging
