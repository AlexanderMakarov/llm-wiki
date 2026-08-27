---
title: "Headless SDK lint pass over a synthetic fixture vault"
type: source
description: "Synthetic Claude SDK-CLI headless run that would be skipped under exclude_headless."
tags: [claude-code, session]
date: 2026-08-03
source_file: raw/sessions/llm-wiki/2026-08-03T18-55-llm-wiki-sdk-cli-headless-lint-pass.md
sessionId: 617d1b10-c14e-41db-7407-170564f312c8
slug: sdk-cli-headless-lint-pass
project: llm-wiki
started: 2026-08-03T18:55:00+00:00
ended: 2026-08-03T19:56:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: chore/headless-demo
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 16
tools_used: [Read, Bash, Grep]
tool_counts: {"Read": 6, "Bash": 2, "Grep": 5}
token_totals: {"input": 24950, "output": 4525}
turn_count: 4
duration_seconds: 3660
is_subagent: false
entrypoint: sdk-cli
promptSource: sdk
is_headless: true
agent: claude-code
---

# Session: 229802be — 2026-08-03

Synthetic Claude SDK-CLI headless run that would be skipped under exclude_headless.

## Conversation

### Turn 1 — User

Run the lint rules against the fixture vault and report only errors.

### Turn 2 — Assistant

Scanned the fixture. Four structural rules are clean; two warning-severity findings remain on stub pages that the fixture deliberately leaves unfinished.

This transcript is authored demo material — not a captured session — so paths stay under `/home/USER/code/llm-wiki`.

### Turn 3 — User

Exit non-zero on warnings too.

### Turn 4 — Assistant

Re-ran with the stricter gate. The two stub warnings now fail the pass, matching what `lint --fail-on warnings` would do on a real vault.

## Subjects

- [[Lint Rules]]
- [[Session Adapters]]
- [[Incremental Sync]]
