---
title: "Split the search index into per-project chunks"
type: source
description: "A single index file was downloading everything up front; it is now chunked and loaded on demand."
tags: [session]
date: 2026-08-07
source_file: raw/sessions/llm-wiki/2026-08-07T19-20-llm-wiki-search-index-chunks.md
sessionId: daa52c18-cbda-2583-4da8-7bb0c4081ffd
slug: search-index-chunks
project: llm-wiki
started: 2026-08-07T19:20:00+00:00
ended: 2026-08-07T19:46:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: perf/search
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 14
tools_used: [Read, Edit, Bash, Glob]
tool_counts: {"Read": 8, "Edit": 4, "Bash": 7, "Glob": 3}
token_totals: {"input": 20800, "output": 3800}
turn_count: 4
duration_seconds: 1560
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 70a5992d — 2026-08-07

A single index file was downloading everything up front; it is now chunked and loaded on demand.

## Conversation

### Turn 1 — User

The site takes a while before search works on a big vault.

### Turn 2 — Assistant

The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed.

On the demo corpus the difference is invisible. On a vault with a thousand sessions it is the difference between a pause and none.

### Turn 3 — User

Does that break search when the page is opened from disk?

### Turn 4 — Assistant

Good catch — it would have. The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches.

## Subjects

- [[Static Site]]
- [[Session Metadata]]
- [[Deployment]]
