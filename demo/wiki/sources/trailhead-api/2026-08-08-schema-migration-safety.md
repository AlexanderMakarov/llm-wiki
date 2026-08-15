---
title: "Make migrations safe to run twice"
type: source
tags: [session, session-transcript, trailhead-api, claude, sqlite-migrations, idempotency, partial-recovery, migration-safety]
date: 2026-08-08
source_file: raw/sessions/trailhead-api/2026-08-08T16-29-trailhead-api-schema-migration-safety.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

A partially applied database migration left the schema in an unrunnable state. Each migration step now checks preconditions before applying, and the runner records individual step completion rather than marking the entire migration done at the end. This enables safe re-running of interrupted migrations to completion. A test was added to verify the behavior, though rollback scenarios remain out of scope.

## Key Claims

- A migration that fails partway through prevents the entire migration from being re-run
- Each migration step now idempotently checks whether it has already been applied and skips if so
- The migration runner tracks individual step completion rather than marking the whole migration as done at the end
- Added test coverage for the failure scenario: interrupt a migration mid-run and successfully resume it  
- Rollback semantics were explicitly out of scope for this fix (would require separate down steps per migration)

## Key Quotes

> "Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column." — Explains the idempotency strategy: precondition checks prevent duplicate operations

> "The runner records each completed step separately instead of marking the whole migration done at the end." — Key architectural change enabling resumability after interruption

> "No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted." — Clarifies the scope boundary and the tradeoff

## Connections

- [[SQLite]] — the specific database system where migrations are applied
- [[Database Migrations]] — the pattern improved to handle partial failures safely

## Contradictions

None noted.