---
title: "Ingest arbitrary documents alongside sessions"
type: source
description: "Added a path for pulling documents into the vault so the wiki is not limited to transcripts."
tags: [session]
date: 2026-08-08
source_file: raw/sessions/llm-wiki/2026-08-08T21-46-llm-wiki-docs-ingest-pipeline.md
sessionId: 5a03da90-a6dc-db54-f241-dbab3701d3fd
slug: docs-ingest-pipeline
project: llm-wiki
started: 2026-08-08T21:46:00+00:00
ended: 2026-08-08T22:26:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/add-docs
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 24
tools_used: [Read, Edit, Bash, WebFetch]
tool_counts: {"Read": 3, "Edit": 6, "Bash": 2, "WebFetch": 5}
token_totals: {"input": 22460, "output": 4090}
turn_count: 4
duration_seconds: 2400
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: 1e4adc4d — 2026-08-08

Added a path for pulling documents into the vault so the wiki is not limited to transcripts.

## Conversation

### Turn 1 — User

I want reference documents in the wiki, not just my sessions.

### Turn 2 — Assistant

Added an ingest path that takes a file, a folder or a URL, converts it to Markdown, and lands it beside the sessions as immutable input. It is then synthesised into a source page like anything else.

Duplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy.

### Turn 3 — User

What happens if the document changed since I added it?

### Turn 4 — Assistant

You get a second copy under a new slug, and the original stays. There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing.

## Subjects

- [[Document Ingest]]
- [[Wiki Synthesis]]
- [[Markdown]]
- [[Incremental Sync]]
