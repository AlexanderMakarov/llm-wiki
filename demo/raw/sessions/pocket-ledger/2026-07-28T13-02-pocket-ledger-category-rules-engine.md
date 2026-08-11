---
title: "Add a rules engine for transaction categories"
type: source
description: "Replaced a hardcoded keyword map with ordered user-defined rules."
tags: [session]
date: 2026-07-28
source_file: raw/sessions/pocket-ledger/2026-07-28T13-02-pocket-ledger-category-rules-engine.md
sessionId: deea060d-b6b9-5111-dfe5-d62464723a9b
slug: category-rules-engine
project: pocket-ledger
started: 2026-07-28T13:02:00+00:00
ended: 2026-07-28T13:30:00+00:00
cwd: /home/USER/code/pocket-ledger
gitBranch: feat/rules
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 7
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 2, "Edit": 5, "Bash": 8}
token_totals: {"input": 15820, "output": 2930}
turn_count: 4
duration_seconds: 1680
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: cursor-cli
---

# Session: f61b3904 — 2026-07-28

Replaced a hardcoded keyword map with ordered user-defined rules.

## Conversation

### Turn 1 — User

Category matching is a giant if-chain. I want to define my own rules.

### Turn 2 — Assistant

Replaced it with an ordered rule list loaded from config: each rule has a matcher and a category, first match wins, and an explicit fallback catches the rest.

Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental.

### Turn 3 — User

Can a rule match on amount as well as description?

### Turn 4 — Assistant

Yes, and the two combine with an implicit and. There is a test for a rule matching only above a threshold, since that was the case the old code could not express at all.

## Subjects

- [[Python]]
- [[Configuration]]
