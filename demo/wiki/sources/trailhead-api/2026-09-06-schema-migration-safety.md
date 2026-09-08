---
title: "Make migrations safe to run twice"
type: source
tags: [session, session-transcript, trailhead-api, claude, idempotent-migrations, schema-migrations, migration-runner, sqlite-migrations, migration-testing]
date: 2026-09-06
source_file: raw/sessions/trailhead-api/2026-09-06T16-29-trailhead-api-schema-migration-safety.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

A migration that failed partway through left the **trailhead-api** schema in a state where the same migration could not be run again. The work made each migration step idempotent by checking preconditions before applying changes, so a re-run skips steps that already succeeded instead of erroring on duplicate schema objects. The runner was changed to record completion per step rather than marking the entire migration finished only at the end, and a test was added that stops a migration mid-flight and then runs it again to completion. Rollback was explicitly left out of scope: only forward re-runs are safe; reversing changes would require down migrations per step.

## Key Claims

- Each migration step checks its own precondition so re-running skips what already applied rather than failing on a duplicate column or similar conflict.
- The migration runner records each completed step separately instead of treating the whole migration as done only after the final step.
- A test interrupts a migration midway and re-runs it to completion to guard the idempotent forward path.
- Idempotency applies to forward runs only; rollback would need a down step per migration and was not implemented because the incident did not justify that larger change.

## Key Quotes

> "Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column." — core idempotent-forward design

> "The runner records each completed step separately instead of marking the whole migration done at the end." — why partial failure no longer blocks re-run

> "No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted." — explicit scope boundary on rollback

## Connections

- [[trailhead-api]] (project) — codebase where migration safety and the interrupt/re-run test were implemented
  - fact: Migrations on this project were refactored for per-step idempotency after a half-applied run blocked retries.
- [[SQLite]] (entity) — storage layer implied by schema migrations and duplicate-column failure mode
  - fact: Failure mode described as duplicate column on re-run, consistent with SQLite-style incremental schema changes.
- [[REST API]] (concept) — service context for the trailhead-api project alongside persisted schema
  - fact: Session subjects tie migration work to the API project’s data layer, not a standalone migration tool repo.
