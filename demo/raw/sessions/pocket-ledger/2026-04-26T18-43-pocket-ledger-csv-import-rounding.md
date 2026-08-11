---
title: "Fix cent-rounding drift on imported statements"
type: source
description: "Repeated float rounding was losing a cent per few hundred rows; switched to integer minor units."
tags: [session]
date: 2026-04-26
source_file: raw/sessions/pocket-ledger/2026-04-26T18-43-pocket-ledger-csv-import-rounding.md
sessionId: f62969e4-7cfc-40c1-2efb-5b61bdad2f36
slug: csv-import-rounding
project: pocket-ledger
started: 2026-04-26T18:43:00+00:00
ended: 2026-04-26T19:08:00+00:00
cwd: /home/USER/code/pocket-ledger
gitBranch: fix/rounding
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 11
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 3, "Edit": 6, "Bash": 2}
token_totals: {"input": 5030, "output": 1045}
turn_count: 4
duration_seconds: 1500
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: a8495f44 — 2026-04-26

Repeated float rounding was losing a cent per few hundred rows; switched to integer minor units.

## Conversation

### Turn 1 — User

Imported totals are off by a few cents against the statement.

### Turn 2 — Assistant

Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge.

Added a regression test with a fixture that reproduced the drift — it was off by four cents over six hundred rows before the change and exact after.

### Turn 3 — User

Any migration needed for existing data?

### Turn 4 — Assistant

No. Stored values are re-parsed from the original statements on import, so the fix applies on the next run without touching anything already saved.

## Subjects

- [[Python]]
- [[pytest]]
- [[Data Import]]
