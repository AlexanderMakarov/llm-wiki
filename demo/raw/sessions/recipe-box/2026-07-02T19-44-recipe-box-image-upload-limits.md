---
title: "Validate image uploads before they reach storage"
type: source
description: "Oversized and mistyped uploads were rejected only after being written."
tags: [session]
date: 2026-07-02
source_file: raw/sessions/recipe-box/2026-07-02T19-44-recipe-box-image-upload-limits.md
sessionId: c2e15801-8717-5630-328c-2fc047726f7d
slug: image-upload-limits
project: recipe-box
started: 2026-07-02T19:44:00+00:00
ended: 2026-07-02T20:14:00+00:00
cwd: /home/USER/code/recipe-box
gitBranch: feat/uploads
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 23
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 3, "Edit": 6, "Bash": 2}
token_totals: {"input": 10840, "output": 2060}
turn_count: 4
duration_seconds: 1800
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 30c23495 — 2026-07-02

Oversized and mistyped uploads were rejected only after being written.

## Conversation

### Turn 1 — User

Someone uploaded a video and it was stored before anything complained.

### Turn 2 — Assistant

Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered.

The error names the limit and the detected type, since the previous message said only that the upload failed.

### Turn 3 — User

What is the cap?

### Turn 4 — Assistant

Configurable, defaulting to eight megabytes. The cap is enforced during the read, so an attempt to send more is cut off rather than measured after the fact.

## Subjects

- [[Web App]]
- [[Validation]]
