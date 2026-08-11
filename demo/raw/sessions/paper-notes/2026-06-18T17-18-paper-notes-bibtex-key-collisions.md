---
title: "Resolve citation key collisions on import"
type: source
description: "Two papers by the same author in the same year overwrote each other."
tags: [session]
date: 2026-06-18
source_file: raw/sessions/paper-notes/2026-06-18T17-18-paper-notes-bibtex-key-collisions.md
sessionId: 40f17e8e-b4cc-0941-3154-29623d27c8b8
slug: bibtex-key-collisions
project: paper-notes
started: 2026-06-18T17:18:00+00:00
ended: 2026-06-18T18:18:00+00:00
cwd: /home/USER/code/paper-notes
gitBranch: fix/bibtex
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 13
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 8, "Edit": 4, "Bash": 7}
token_totals: {"input": 9180, "output": 1770}
turn_count: 4
duration_seconds: 3600
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: cursor-cli
---

# Session: aeac229b — 2026-06-18

Two papers by the same author in the same year overwrote each other.

## Conversation

### Turn 1 — User

Importing two papers by the same author from the same year silently keeps one.

### Turn 2 — Assistant

Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly.

Existing keys are left alone so citations already written do not shift.

### Turn 3 — User

What if the same paper is imported twice?

### Turn 4 — Assistant

That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers.

## Subjects

- [[Markdown]]
- [[Data Import]]
- [[Validation]]
