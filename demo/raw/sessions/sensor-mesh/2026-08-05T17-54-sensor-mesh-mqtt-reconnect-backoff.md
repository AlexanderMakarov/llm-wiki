---
title: "Add backoff to broker reconnection"
type: source
description: "A dropped broker connection produced a tight reconnect loop."
tags: [session]
date: 2026-08-05
source_file: raw/sessions/sensor-mesh/2026-08-05T17-54-sensor-mesh-mqtt-reconnect-backoff.md
sessionId: 39707e8f-b349-b607-c245-eb0d252d4e66
slug: mqtt-reconnect-backoff
project: sensor-mesh
started: 2026-08-05T17:54:00+00:00
ended: 2026-08-05T18:50:00+00:00
cwd: /home/USER/code/sensor-mesh
gitBranch: fix/reconnect
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 27
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 6, "Edit": 2, "Bash": 5}
token_totals: {"input": 19140, "output": 3510}
turn_count: 4
duration_seconds: 3360
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: f0a28657 — 2026-08-05

A dropped broker connection produced a tight reconnect loop.

## Conversation

### Turn 1 — User

When the broker goes down the logs fill up in seconds.

### Turn 2 — Assistant

The reconnect had no delay. It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep.

The log line moved to a summary — one line per attempt with the current delay, rather than one per failure.

### Turn 3 — User

Does it give up eventually?

### Turn 4 — Assistant

No, it keeps retrying at the ceiling. For a background collector, continuing to try is more useful than exiting and needing supervision to restart it.

## Subjects

- [[Time Series]]
- [[Observability]]
