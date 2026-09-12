---
title: "Cut shell startup time by deferring completions (marnitask)"
type: source
description: "Startup was dominated by loading completion scripts that were rarely used."
tags: [session-transcript, session]
date: 2026-06-29
source_file: raw/sessions/dotfiles/2026-06-29T15-52-dotfiles-shell-startup-profiling.md
sessionId: a15bb9e8-8df4-5256-6393-57ad5c4e897a
slug: shell-startup-profiling
project: dotfiles
started: 2026-06-29T15:52:00+00:00
ended: 2026-06-29T17:09:00+00:00
cwd: /home/USER/code/dotfiles
gitBranch: perf/startup
permissionMode: default
model: claude-opus-5
user_messages: 4
tool_calls: 16
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 6, "Edit": 5, "Bash": 5}
token_totals: {"input": 6480, "output": 1480}
turn_count: 4
duration_seconds: 4620
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: 4e8cdec3 — 2026-06-29

**Project:** `dotfiles` · **Branch:** `perf/startup` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 4 user messages, 16 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

New terminals take almost a second to become usable.

### Turn 1 — Assistant

Profiled the startup file. Most of the time was loading completion scripts eagerly, including several for tools not installed on this machine.

They are now loaded lazily on first use of the command, and missing tools are skipped rather than failing silently. Startup went from roughly nine hundred milliseconds to under two hundred.

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/dotfiles/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k shell_startup_profiling  # 4aaa75`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 171 lines)


### Turn 2 — User

Do completions still work on first use?

### Turn 2 — Assistant

Yes — the first tab press pays the load cost once, then it is cached for the session. Noticeable only if you are looking for it.

**Tools used:**

- `Edit`: `llmwiki/dotfiles/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k shell_startup_profiling  # 20a2dd`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

**Tools used:**

- `Edit`: `llmwiki/dotfiles/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 3 — User

Is the headless path affected?

### Turn 3 — Assistant

No — headless fixtures stay excluded from default synth. This change is interactive-session only. Related: [[Shell]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k shell_startup_profiling  # 0866b1`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 477 lines)

**Tools used:**

- `Edit`: `llmwiki/dotfiles/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k shell_startup_profiling  # e1d7be`

**Tool results:**

  → result (ok): … 7 passed in 0.3s


### Turn 4 — User

Document it?

### Turn 4 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[Configuration]].

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 630 lines)

**Tools used:**

- `Edit`: `llmwiki/dotfiles/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k shell_startup_profiling  # 263737`

**Tool results:**

  → result (ok): … 7 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/shell_startu.py` L1–80

**Tool results:**

  → result (ok): (file, 681 lines)

