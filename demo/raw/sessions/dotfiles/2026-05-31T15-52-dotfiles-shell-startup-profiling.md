---
title: "Cut shell startup time by deferring completions"
type: source
description: "Startup was dominated by loading completion scripts that were rarely used."
tags: [session]
date: 2026-05-31
source_file: raw/sessions/dotfiles/2026-05-31T15-52-dotfiles-shell-startup-profiling.md
sessionId: a15bb9e8-8df4-5256-6393-57ad5c4e897a
slug: shell-startup-profiling
project: dotfiles
started: 2026-05-31T15:52:00+00:00
ended: 2026-05-31T16:38:00+00:00
cwd: /home/USER/code/dotfiles
gitBranch: perf/startup
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 26
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 6, "Edit": 2, "Bash": 5}
token_totals: {"input": 7520, "output": 1480}
turn_count: 4
duration_seconds: 2760
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: 4e8cdec3 — 2026-05-31

Startup was dominated by loading completion scripts that were rarely used.

## Conversation

### Turn 1 — User

New terminals take almost a second to become usable.

### Turn 2 — Assistant

Profiled the startup file. Most of the time was loading completion scripts eagerly, including several for tools not installed on this machine.

They are now loaded lazily on first use of the command, and missing tools are skipped rather than failing silently. Startup went from roughly nine hundred milliseconds to under two hundred.

### Turn 3 — User

Do completions still work on first use?

### Turn 4 — Assistant

Yes — the first tab press pays the load cost once, then it is cached for the session. Noticeable only if you are looking for it.

## Subjects

- [[Shell]]
- [[Configuration]]
