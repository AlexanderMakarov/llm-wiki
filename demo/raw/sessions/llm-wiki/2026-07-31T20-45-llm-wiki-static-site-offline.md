---
title: "Make the built site work without a server or a network"
type: source
description: "Vendored the graph library and moved state into a script tag so the site opens from a file."
tags: [session]
date: 2026-07-31
source_file: raw/sessions/llm-wiki/2026-07-31T20-45-llm-wiki-static-site-offline.md
sessionId: 1dab43b8-145a-b03e-493a-2b2d1f3ccb04
slug: static-site-offline
project: llm-wiki
started: 2026-07-31T20:45:00+00:00
ended: 2026-07-31T21:20:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/offline
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 12
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 3, "Edit": 6, "Bash": 2}
token_totals: {"input": 16650, "output": 3075}
turn_count: 4
duration_seconds: 2100
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 00503fd4 — 2026-07-31

Vendored the graph library and moved state into a script tag so the site opens from a file.

## Conversation

### Turn 1 — User

Can I just open the site from disk, or do I need to serve it?

### Turn 2 — Assistant

You can now. Two things were in the way. The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence.

The bigger one: page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk.

### Turn 3 — User

What still needs a server?

### Turn 4 — Assistant

Only the candidates page, which posts review decisions to a small endpoint. Everything else — home, projects, sessions, topics, search, graph — is static.

## Subjects

- [[Static Site]]
- [[Knowledge Graph]]
- [[Deployment]]
