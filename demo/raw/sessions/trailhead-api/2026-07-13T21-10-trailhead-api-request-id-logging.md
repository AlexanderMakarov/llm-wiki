---
title: "Thread a request id through the log output"
type: source
description: "Concurrent requests interleaved in the log with no way to separate them."
tags: [session]
date: 2026-07-13
source_file: raw/sessions/trailhead-api/2026-07-13T21-10-trailhead-api-request-id-logging.md
sessionId: aaaf854c-68f8-76e0-040c-f2ae4a563ecc
slug: request-id-logging
project: trailhead-api
started: 2026-07-13T21:10:00+00:00
ended: 2026-07-13T21:54:00+00:00
cwd: /home/USER/code/trailhead-api
gitBranch: chore/logging
permissionMode: default
model: gpt-5-codex
user_messages: 2
tool_calls: 10
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 5, "Edit": 8, "Bash": 4}
token_totals: {"input": 12500, "output": 2350}
turn_count: 4
duration_seconds: 2640
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: codex-cli
---

# Session: 4a96525b — 2026-07-13

Concurrent requests interleaved in the log with no way to separate them.

## Conversation

### Turn 1 — User

I cannot follow a single request through the logs when there is any traffic.

### Turn 2 — Assistant

Added a request id generated at the edge, stored in a context variable, and included by the log formatter on every line. Nothing has to pass it explicitly.

It is also returned as a response header, so a report about a specific failed request can be traced directly.

### Turn 3 — User

Does it survive a background task?

### Turn 4 — Assistant

Only if the task is spawned from the request context. Anything scheduled outside it gets a fresh id, which is correct — it is a different unit of work.

## Subjects

- [[REST API]]
- [[Observability]]
- [[Python]]
