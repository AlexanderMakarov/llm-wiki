---
title: "Extract readable text from two-column PDFs"
type: source
description: "Column-aware extraction replaced a naive reader that interleaved lines."
tags: [session]
date: 2026-07-22
source_file: raw/sessions/paper-notes/2026-07-22T23-36-paper-notes-pdf-text-extraction.md
sessionId: 86b8651c-cb11-bd66-b6ad-d1694ead7fec
slug: pdf-text-extraction
project: paper-notes
started: 2026-07-22T23:36:00+00:00
ended: 2026-07-23T00:34:00+00:00
cwd: /home/USER/code/paper-notes
gitBranch: feat/pdf
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 20
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 7, "Edit": 3, "Bash": 6}
token_totals: {"input": 14160, "output": 2640}
turn_count: 4
duration_seconds: 3480
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: ef964a20 — 2026-07-22

Column-aware extraction replaced a naive reader that interleaved lines.

## Conversation

### Turn 1 — User

Extracted text from two-column papers is interleaved nonsense.

### Turn 2 — Assistant

The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on.

Single-column pages take the same path and are unaffected, since one detected column is just the page.

### Turn 3 — User

Does it handle a paper that switches layout mid-document?

### Turn 4 — Assistant

Yes — detection runs per page rather than once per document, so a single-column abstract followed by two-column body works.

## Subjects

- [[Markdown]]
- [[Data Import]]
- [[Python]]
