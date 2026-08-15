---
title: "Move list endpoints from offset to cursor pagination"
type: source
tags: [session, session-transcript, trailhead-api, claude, cursor-pagination, offset-pagination-bug, pagination-correctness, backward-compatibility]
date: 2026-05-09
source_file: raw/sessions/trailhead-api/2026-05-09T13-26-trailhead-api-pagination-cursors.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session identified and resolved a pagination bug where clients missed records during multi-page scans when new rows were inserted mid-scan. The fix migrated from offset-based pagination to opaque cursor-based pagination, using a stable sort column plus primary key as a tiebreaker to ensure consistent ordering regardless of concurrent inserts. Backward compatibility was preserved by accepting the old offset parameter with a deprecation header, deferring removal to a future major version.

## Key Claims

- Offset pagination skips rows when records are inserted before the current offset during pagination, because the insertion shifts row positions and causes the next page to duplicate skipped entries.
- Cursor-based pagination with an opaque token encoding both the stable sort column value and primary key prevents row loss, since the cursor position is independent of absolute row counts.
- The old offset parameter remains functional with a deprecation header to avoid an immediate breaking change; removal is deferred to a major version bump.

## Key Quotes

> "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one." — root cause analysis

> "The cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan." — how the solution preserves consistency

> "Yes, for now — it still works and returns a deprecation header. Removing it is a breaking change and belongs in a version bump." — backward compatibility rationale

## Connections

- [[REST API]] — list endpoints migrated to cursor pagination
- [[SQLite]] — underlying storage layer for paginated queries
- [[Python]] — implementation language