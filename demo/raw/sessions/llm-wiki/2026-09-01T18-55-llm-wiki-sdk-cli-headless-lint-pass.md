---
title: "Headless SDK lint pass over a synthetic fixture vault"
type: source
description: "Synthetic Claude SDK-CLI headless run that would be skipped under exclude_headless."
tags: [session-transcript, claude-code, session]
date: 2026-09-01
source_file: raw/sessions/llm-wiki/2026-09-01T18-55-llm-wiki-sdk-cli-headless-lint-pass.md
sessionId: 617d1b10-c14e-41db-7407-170564f312c8
slug: sdk-cli-headless-lint-pass
project: llm-wiki
started: 2026-09-01T18:55:00+00:00
ended: 2026-09-01T19:20:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: chore/headless-demo
permissionMode: default
model: claude-opus-5
user_messages: 1
tool_calls: 3
tools_used: [Read, Bash, Grep]
tool_counts: {"Read": 1, "Bash": 1, "Grep": 1}
token_totals: {"input": 3060, "output": 485}
turn_count: 1
duration_seconds: 1500
is_subagent: false
entrypoint: sdk-cli
promptSource: sdk
is_headless: true
agent: claude-code
---

# Session: 229802be — 2026-09-01

**Project:** `llm-wiki` · **Branch:** `chore/headless-demo` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 1 user messages, 3 tool calls, tools used: Read, Bash, Grep.

## Conversation

### Turn 1 — User

Run the lint rules against the fixture vault and report only errors.

### Turn 1 — Assistant

Scanned the fixture. Four structural rules are clean; two warning-severity findings remain on stub pages that the fixture deliberately leaves unfinished.

This transcript is authored demo material — not a captured session — so paths stay under `/home/USER/code/llm-wiki`.

**Tools used:**

- `Read`: `llmwiki/sdk_cli_head.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k sdk_cli_headless_lint_pass  # 2c7d7f`

**Tool results:**

  → result (ok): … 3 passed in 0.1s

**Tools used:**

- `Grep`: pattern `sdk-cli-headless-lint-pass` path `llmwiki/`

**Tool results:**

  → result (ok): llmwiki/cli.py:12: …

Connections: [[Lint Rules]], [[Session Adapters]], [[Incremental Sync]].
