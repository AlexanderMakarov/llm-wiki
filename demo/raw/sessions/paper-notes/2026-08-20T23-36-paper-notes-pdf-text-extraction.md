---
title: "Extract readable text from two-column PDFs"
type: source
description: "Column-aware extraction replaced a naive reader that interleaved lines."
tags: [session-transcript, session]
date: 2026-08-20
source_file: raw/sessions/paper-notes/2026-08-20T23-36-paper-notes-pdf-text-extraction.md
sessionId: 86b8651c-cb11-bd66-b6ad-d1694ead7fec
slug: pdf-text-extraction
project: paper-notes
started: 2026-08-20T23:36:00+00:00
ended: 2026-08-21T00:45:00+00:00
cwd: /home/USER/code/paper-notes
gitBranch: feat/pdf
permissionMode: default
model: claude-opus-5
user_messages: 4
tool_calls: 17
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 6, "Edit": 5, "Bash": 6}
token_totals: {"input": 6920, "output": 1515}
turn_count: 4
duration_seconds: 4140
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: ef964a20 — 2026-08-20

**Project:** `paper-notes` · **Branch:** `feat/pdf` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 4 user messages, 17 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

Extracted text from two-column papers is interleaved nonsense.

### Turn 1 — Assistant

The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on.

Single-column pages take the same path and are unaffected, since one detected column is just the page.

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/paper_notes/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k pdf_text_extraction  # 963e97`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 171 lines)


### Turn 2 — User

Does it handle a paper that switches layout mid-document?

### Turn 2 — Assistant

Yes — detection runs per page rather than once per document, so a single-column abstract followed by two-column body works.

**Tools used:**

- `Edit`: `llmwiki/paper_notes/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k pdf_text_extraction  # dc4108`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

**Tools used:**

- `Edit`: `llmwiki/paper_notes/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 3 — User

What should I commit?

### Turn 3 — Assistant

The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages. Related: [[Python]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k pdf_text_extraction  # a0f547`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 477 lines)

**Tools used:**

- `Edit`: `llmwiki/paper_notes/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k pdf_text_extraction  # 65c7d8`

**Tool results:**

  → result (ok): … 7 passed in 0.3s


### Turn 4 — User

Any lint fallout?

### Turn 4 — Assistant

One warning-severity count mismatch on an old stub — unrelated. The new pages are clean. Related: [[Markdown]].

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 630 lines)

**Tools used:**

- `Edit`: `llmwiki/paper_notes/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k pdf_text_extraction  # 9fd209`

**Tool results:**

  → result (ok): … 7 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/pdf_text_ext.py` L1–80

**Tool results:**

  → result (ok): (file, 681 lines)

**Tools used:**

- `Bash`: `rg -n draxelume wiki/`

**Tool results:**

  → result (ok): wiki/overview.md:14: … draxelume …

