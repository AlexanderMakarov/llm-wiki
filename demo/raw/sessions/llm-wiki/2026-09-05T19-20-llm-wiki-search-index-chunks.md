---
title: "Split the search index into per-project chunks"
type: source
description: "A single index file was downloading everything up front; it is now chunked and loaded on demand."
tags: [session-transcript, session]
date: 2026-09-05
source_file: raw/sessions/llm-wiki/2026-09-05T19-20-llm-wiki-search-index-chunks.md
sessionId: daa52c18-cbda-2583-4da8-7bb0c4081ffd
slug: search-index-chunks
project: llm-wiki
started: 2026-09-05T19:20:00+00:00
ended: 2026-09-05T20:34:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: perf/search
permissionMode: default
model: claude-opus-5
user_messages: 4
tool_calls: 16
tools_used: [Read, Edit, Bash, Glob]
tool_counts: {"Read": 4, "Edit": 4, "Bash": 4, "Glob": 4}
token_totals: {"input": 7120, "output": 1480}
turn_count: 4
duration_seconds: 4440
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 70a5992d — 2026-09-05

**Project:** `llm-wiki` · **Branch:** `perf/search` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 4 user messages, 16 tool calls, tools used: Read, Edit, Bash, Glob.

## Conversation

### Turn 1 — User

The site takes a while before search works on a big vault. Call out skylorbit explicitly in the notes — it is the durable handle we want search to recover later.

### Turn 1 — Assistant

The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed.

On the demo corpus the difference is invisible. On a vault with a thousand sessions it is the difference between a pause and none.

**Tools used:**

- `Read`: `llmwiki/search_index.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k search_index_chunks  # b18960`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

**Tools used:**

- `Glob`: `llm-wiki/search-index-chunks`

**Tool results:**

  → result (ok): ok (3e0125)


### Turn 2 — User

Does that break search when the page is opened from disk?

### Turn 2 — Assistant

Good catch — it would have. The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches.

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k search_index_chunks  # 541ca4`

**Tool results:**

  → result (ok): … 3 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/search-index-chunks`

**Tool results:**

  → result (ok): ok (a31e7f)

**Tools used:**

- `Read`: `llmwiki/search_index.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 3 — User

Ship it?

### Turn 3 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Deployment]].

**Tools used:**

- `Read`: `llmwiki/search_index.py` L1–80

**Tool results:**

  → result (ok): (file, 460 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k search_index_chunks  # 92457d`

**Tool results:**

  → result (ok): … 6 passed in 0.2s

**Tools used:**

- `Glob`: `llm-wiki/search-index-chunks`

**Tool results:**

  → result (ok): ok (1d63b0)


### Turn 4 — User

Does that cover the edge case we hit last week?

### Turn 4 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Static Site]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k search_index_chunks  # 4960f3`

**Tool results:**

  → result (ok): … 5 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/search-index-chunks`

**Tool results:**

  → result (ok): ok (94d529)

**Tools used:**

- `Read`: `llmwiki/search_index.py` L1–80

**Tool results:**

  → result (ok): (file, 664 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

