---
title: "Make migrations safe to run twice"
type: source
description: "A partially applied migration left the schema unrunnable; each step is now idempotent."
tags: [session]
date: 2026-08-08
source_file: raw/sessions/trailhead-api/2026-08-08T16-29-trailhead-api-schema-migration-safety.md
sessionId: 1053f779-5696-9f65-2fef-ebc0609dce2a
slug: schema-migration-safety
project: trailhead-api
started: 2026-08-08T16:29:00+00:00
ended: 2026-08-08T17:16:00+00:00
cwd: /home/USER/code/trailhead-api
gitBranch: chore/migrations
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 6
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 4, "Edit": 7, "Bash": 3}
token_totals: {"input": 23290, "output": 4235}
turn_count: 4
duration_seconds: 2820
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 019741fc — 2026-08-08

A partially applied migration left the schema unrunnable; each step is now idempotent.

## Conversation

### Turn 1 — User

A migration failed halfway and now I cannot run it again.

### Turn 2 — Assistant

Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column. The runner records each completed step separately instead of marking the whole migration done at the end.

Added a test that interrupts a migration mid-way and re-runs it to completion.

### Turn 3 — User

Does that cover a rollback?

### Turn 4 — Assistant

No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted.

## Subjects

- [[SQLite]]
- [[REST API]]
- [[pytest]]
