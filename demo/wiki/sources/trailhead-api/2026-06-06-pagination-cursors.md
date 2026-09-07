---
title: "Move list endpoints from offset to cursor pagination"
type: source
tags: [session, session-transcript, trailhead-api, claude, cursor-pagination, pagination-offset-bug, api-deprecation]
date: 2026-06-06
source_file: raw/sessions/trailhead-api/2026-06-06T13-26-trailhead-api-pagination-cursors.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session resolved a data loss bug in the trailhead-api where offset-based pagination would skip rows when new records were inserted during a client's multi-page scan. The solution migrated list endpoints to cursor-based pagination using opaque tokens that encode both a stable sort column and the primary key, ensuring query ordering remains stable even with concurrent inserts. Backward compatibility was maintained by deprecating (rather than removing) the old offset parameter while continuing to accept it and returning a deprecation header.

## Key Claims

- Offset pagination causes rows to be skipped when records are inserted before the current offset position during a paginated query sequence
- Cursor pagination using opaque tokens encoding (sort_column_value, primary_key) pairs prevents row skipping by maintaining stable ordering across concurrent modifications
- The old offset-based pagination parameter remains functional with a deprecation header to avoid immediate breaking changes
- Removing the old parameter would require a major version bump due to backward compatibility concerns

## Key Quotes

> "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one. I moved to cursor paging keyed on a stable sort column plus the primary key as a tiebreak." — explains the root cause and core solution approach

> "The cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan." — describes how the opaque token design prevents the concurrency race condition

## Connections

- [[REST API]] (concept) — HTTP API with paginated list endpoints
  - fact: Migrated from offset to cursor-based pagination to prevent row skipping during concurrent data modifications
- [[SQLite]] (concept) — database backend storing paginated records  
  - fact: Cursor approach ensures query ordering remains stable even when records are inserted during a scan

## Contradictions

- None identified.