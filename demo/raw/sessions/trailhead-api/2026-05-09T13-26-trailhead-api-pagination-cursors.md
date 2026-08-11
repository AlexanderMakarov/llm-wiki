---
title: "Move list endpoints from offset to cursor pagination"
type: source
description: "Offset paging skipped rows when records were inserted mid-scan; cursors fixed it."
tags: [session]
date: 2026-05-09
source_file: raw/sessions/trailhead-api/2026-05-09T13-26-trailhead-api-pagination-cursors.md
sessionId: c10daf7d-dc65-2ac0-af13-e1cf3304d642
slug: pagination-cursors
project: trailhead-api
started: 2026-05-09T13:26:00+00:00
ended: 2026-05-09T13:58:00+00:00
cwd: /home/USER/code/trailhead-api
gitBranch: feat/pagination
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 16
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 4, "Edit": 7, "Bash": 3}
token_totals: {"input": 5860, "output": 1190}
turn_count: 4
duration_seconds: 1920
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 1a2e076f — 2026-05-09

Offset paging skipped rows when records were inserted mid-scan; cursors fixed it.

## Conversation

### Turn 1 — User

Clients paging through the list endpoint are missing records.

### Turn 2 — Assistant

Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one. I moved to cursor paging keyed on a stable sort column plus the primary key as a tiebreak.

The cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan.

### Turn 3 — User

Is the old parameter still accepted?

### Turn 4 — Assistant

Yes, for now — it still works and returns a deprecation header. Removing it is a breaking change and belongs in a version bump.

## Subjects

- [[REST API]]
- [[SQLite]]
- [[Python]]
