---
title: "Add backoff to broker reconnection"
type: source
description: "A dropped broker connection produced a tight reconnect loop."
tags: [session-transcript, session]
date: 2026-09-03
source_file: raw/sessions/sensor-mesh/2026-09-03T17-54-sensor-mesh-mqtt-reconnect-backoff.md
sessionId: 39707e8f-b349-b607-c245-eb0d252d4e66
slug: mqtt-reconnect-backoff
project: sensor-mesh
started: 2026-09-03T17:54:00+00:00
ended: 2026-09-03T18:30:00+00:00
cwd: /home/USER/code/sensor-mesh
gitBranch: fix/reconnect
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 7
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 2, "Edit": 2, "Bash": 3}
token_totals: {"input": 4160, "output": 805}
turn_count: 2
duration_seconds: 2160
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: f0a28657 — 2026-09-03

**Project:** `sensor-mesh` · **Branch:** `fix/reconnect` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 2 user messages, 7 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

When the broker goes down the logs fill up in seconds.

### Turn 1 — Assistant

The reconnect had no delay. It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep.

The log line moved to a summary — one line per attempt with the current delay, rather than one per failure.

**Tools used:**

- `Read`: `llmwiki/mqtt_reconne.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/sensor_mesh/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k mqtt_reconnect_backoff  # fa19fb`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 2 — User

Does it give up eventually?

### Turn 2 — Assistant

No, it keeps retrying at the ceiling. For a background collector, continuing to try is more useful than exiting and needing supervision to restart it.

**Tools used:**

- `Edit`: `llmwiki/sensor_mesh/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k mqtt_reconnect_backoff  # 5d64f7`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/mqtt_reconne.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

**Tools used:**

- `Bash`: `rg -n farnodeck wiki/`

**Tool results:**

  → result (ok): wiki/overview.md:14: … farnodeck …

Connections: [[Time Series]], [[Observability]].
