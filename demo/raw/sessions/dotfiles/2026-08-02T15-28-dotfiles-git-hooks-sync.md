---
title: "Version the git hooks instead of copying them"
type: source
description: "Hooks drifted between machines because they lived outside the repository."
tags: [session]
date: 2026-08-02
source_file: raw/sessions/dotfiles/2026-08-02T15-28-dotfiles-git-hooks-sync.md
sessionId: 2ea379b6-df3d-18f9-9f70-dac6b22c8792
slug: git-hooks-sync
project: dotfiles
started: 2026-08-02T15:28:00+00:00
ended: 2026-08-02T16:10:00+00:00
cwd: /home/USER/code/dotfiles
gitBranch: feat/hooks
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 17
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 4, "Edit": 7, "Bash": 3}
token_totals: {"input": 17480, "output": 3220}
turn_count: 4
duration_seconds: 2520
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: cursor-cli
---

# Session: e69a9815 — 2026-08-02

Hooks drifted between machines because they lived outside the repository.

## Conversation

### Turn 1 — User

My pre-push hook is different on each machine.

### Turn 2 — Assistant

Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull.

The setup script wires the path, and the hook itself checks only the files in the push rather than the whole tree, which keeps it fast enough that nobody is tempted to skip it.

### Turn 3 — User

What if someone needs to bypass it?

### Turn 4 — Assistant

The standard no-verify flag still works. The point is that skipping is a deliberate act rather than the default state.

## Subjects

- [[Shell]]
- [[Git]]
- [[Configuration]]
