---
title: "Make migrations safe to run twice"
type: source
tags: [session, session-transcript, trailhead-api, claude, idempotent-migrations, migration-recovery, sqlite, schema-safety]
date: 2026-09-05
source_file: raw/sessions/trailhead-api/2026-09-05T16-29-trailhead-api-schema-migration-safety.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

A partially applied database migration left the trailhead-api schema in an unrunnable state. The assistant made each migration step idempotent by adding precondition checks, and changed the runner to record completion per-step rather than marking the entire migration complete at the end. This allows interrupted migrations to be re-run without failing on duplicate changes. A test was added to verify the recovery scenario.

## Key Claims

- A partially applied migration left the database schema in an unrunnable state
- Each migration step now checks preconditions before executing to avoid duplicate-column errors
- Migration completion is recorded per-step rather than for the entire migration
- Re-running a partially-applied migration skips already-applied steps instead of failing
- A test was added that interrupts a migration mid-way and verifies re-run completes successfully
- Rollback scenarios are not covered by this change; only forward runs are idempotent

## Key Quotes

> "Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column." — Core strategy for making migrations repeatable without manual intervention

> "No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted." — Clarifies the intentional scope limitation of the fix

## Connections

- [[trailhead-api]] (project) — API backend where migration resilience was improved
  - fact: A partially applied migration left the schema unrunnable, triggering the safety refactor
- [[SQLite]] (technology) — Relational database system for persistent state
  - fact: Migration steps now check preconditions to prevent duplicate-column errors when re-run
- [[Database Migrations]] (concept) — Schema versioning pattern requiring careful state tracking
  - fact: Per-step completion recording enables recovery from interrupted migrations
- [[pytest]] (technology) — Testing framework used to verify failure scenarios
  - fact: Test added that interrupts a migration mid-way and verifies successful re-run to completion