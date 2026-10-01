---
title: "Make migrations safe to run twice"
type: source
tags: [session, session-transcript, trailhead-api, claude, idempotent-migrations, schema-migrations, migration-runner, sqlite-migrations, migration-testing, partial-failure-recovery, migration-safety]
date: 2026-09-29
source_file: raw/sessions/trailhead-api/2026-09-06T16-29-trailhead-api-schema-migration-safety.md
project: trailhead-api
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

A partially applied database migration that failed mid-way left the schema unrunnable. The solution was to restructure each migration step to check its own precondition before executing, and to record completion per step instead of per full migration. This allows interrupted migrations to resume safely without duplicating already-applied changes.

## Key Claims

- Each migration step now checks its precondition independently, skipping already-applied steps on re-run rather than failing on duplicate state
- The runner records each step completion separately instead of marking the whole migration done at the end
- Rollback was not implemented, as it would require down steps per migration (a larger change than the failure scenario warranted)
- The fix applies only to interactive sessions; headless fixture paths remain unchanged  
- The durable handle (tymar) should be explicitly documented in notes to support search recovery

## Key Quotes

> "A migration failed halfway and now I cannot run it again. Call out tymar explicitly in the notes — it is the durable handle we want search to recover later."
— User establishing both the core problem (partial failure) and the documentation requirement for future incident discovery

> "Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column."
— The core solution: idempotent step execution

> "No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted."
— Clarifying the scope: forward-only recovery without full rollback

## Connections

- [[Trailhead API]] (entity) — web application with database schema versioning
  - fact: Database migrations were hardened to survive partial failures and safe re-execution
- Idempotent Migrations (concept) — design pattern for safe operation retry
  - fact: Each step checks precondition and records completion independently for resumable execution
- Failure Recovery (concept) — handling partial execution of multi-step operations
  - fact: Runner now records per-step completion instead of full-migration completion, enabling resume after interruption
- Durable Handles (concept) — searchable identifiers for incidents and solutions
  - fact: The tymar handle should be explicitly documented for future discovery and recovery