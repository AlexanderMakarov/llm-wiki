---
title: "Refactor the adapter registry so contrib adapters stay opt-in"
type: source
description: "Split the adapter registry so core adapters auto-detect while contrib ones require an explicit flag."
tags: [session]
date: 2026-04-12
source_file: raw/sessions/llm-wiki/2026-04-12T00-00-llm-wiki-adapter-registry-refactor.md
sessionId: e315386e-33e6-db99-c1d5-07a51dedec46
slug: adapter-registry-refactor
project: llm-wiki
started: 2026-04-12T00:00:00+00:00
ended: 2026-04-12T00:18:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/adapters
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 6
tools_used: [Read, Edit, Bash, Grep]
tool_counts: {"Read": 2, "Edit": 5, "Bash": 8, "Grep": 4}
token_totals: {"input": 4200, "output": 900}
turn_count: 4
duration_seconds: 1080
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 47af34d7 — 2026-04-12

Split the adapter registry so core adapters auto-detect while contrib ones require an explicit flag.

## Conversation

### Turn 1 — User

The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for. Can we make core auto-detect and contrib opt-in?

### Turn 2 — Assistant

Looked at the registry. `llmwiki/adapters/` holds the core two — Claude Code and Codex CLI — and everything else lives under `contrib/`. The detection loop treats both directories identically, which is the bug.

I split the lookup: core adapters are probed on every `sync`, contrib ones only when named with `--adapter` or enabled in config. Added a test that a contrib adapter stays silent on a default sync even when its session store exists.

### Turn 3 — User

Good. Make sure `llmwiki adapters` still lists everything so people can discover them.

### Turn 4 — Assistant

It does — listing is separate from activation. `llmwiki adapters --wide` shows every adapter with a present/absent column, and contrib rows now carry an `opt-in` marker so the distinction is visible before you run a sync.

## Subjects

- [[Session Adapters]]
- [[Claude Code]]
- [[Codex CLI]]
- [[Contrib Adapters]]
- [[Incremental Sync]]
