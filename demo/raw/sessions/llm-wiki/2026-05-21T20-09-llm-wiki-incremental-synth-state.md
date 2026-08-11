---
title: "Stop re-synthesising sources that have not changed"
type: source
description: "Traced why a second synth run re-processed everything and fixed the state comparison."
tags: [session]
date: 2026-05-21
source_file: raw/sessions/llm-wiki/2026-05-21T20-09-llm-wiki-incremental-synth-state.md
sessionId: 4afa19bd-7b56-2c1a-0bcc-3cfe33e62874
slug: incremental-synth-state
project: llm-wiki
started: 2026-05-21T20:09:00+00:00
ended: 2026-05-21T20:48:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: fix/synth-state
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 21
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 5, "Edit": 8, "Bash": 4}
token_totals: {"input": 6690, "output": 1335}
turn_count: 4
duration_seconds: 2340
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 9ca1b8e1 — 2026-05-21

Traced why a second synth run re-processed everything and fixed the state comparison.

## Conversation

### Turn 1 — User

Running synth twice in a row re-synthesises everything. It should be a no-op the second time.

### Turn 2 — Assistant

Found it. The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new.

Fixed the comparison and added a small epsilon so filesystems with coarse timestamp resolution do not flip the result. A second run is now genuinely a no-op — the run summary reports `skipped` for every source.

### Turn 3 — User

Does that survive a fresh clone?

### Turn 4 — Assistant

No, and that is worth knowing. Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus. Content hashing would fix it properly; the state file would need a migration. I have written it up rather than changing it here.

## Subjects

- [[Incremental Sync]]
- [[Wiki Synthesis]]
- [[Session Adapters]]
