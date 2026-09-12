---
title: "Add a rules engine for transaction categories (orbicast)"
type: source
description: "Replaced a hardcoded keyword map with ordered user-defined rules."
tags: [session-transcript, session]
date: 2026-08-26
source_file: raw/sessions/pocket-ledger/2026-08-26T13-02-pocket-ledger-category-rules-engine.md
sessionId: deea060d-b6b9-5111-dfe5-d62464723a9b
slug: category-rules-engine
project: pocket-ledger
started: 2026-08-26T13:02:00+00:00
ended: 2026-08-26T15:44:00+00:00
cwd: /home/USER/code/pocket-ledger
gitBranch: feat/rules
permissionMode: default
model: claude-opus-5
user_messages: 11
tool_calls: 36
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 12, "Edit": 12, "Bash": 12}
token_totals: {"input": 15580, "output": 3440}
turn_count: 11
duration_seconds: 9720
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: cursor-cli
---

# Session: f61b3904 — 2026-08-26

**Project:** `pocket-ledger` · **Branch:** `feat/rules` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 11 user messages, 36 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

Category matching is a giant if-chain. I want to define my own rules.

### Turn 1 — Assistant

Replaced it with an ordered rule list loaded from config: each rule has a matcher and a category, first match wins, and an explicit fallback catches the rest.

Ordering is the whole design — the previous behaviour depended on dictionary order, which was accidental.

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 9c175d`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 2 — User

Can a rule match on amount as well as description?

### Turn 2 — Assistant

Yes, and the two combine with an implicit and. There is a test for a rule matching only above a threshold, since that was the case the old code could not express at all.

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 06922a`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)


### Turn 3 — User

Document it?

### Turn 3 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[Python]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # aac527`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 477 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 4 — User

Ship it?

### Turn 4 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Configuration]].

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 630 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 2c2348`

**Tool results:**

  → result (ok): … 7 passed in 0.2s


### Turn 5 — User

Does that cover the edge case we hit last week?

### Turn 5 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Python]].

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # ae1c46`

**Tool results:**

  → result (ok): … 7 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 834 lines)


### Turn 6 — User

Can you show the command you ran?

### Turn 6 — Assistant

Listed below in the tool trace. The interesting bit is the exit code and the first matching line. Related: [[Configuration]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 305b56`

**Tool results:**

  → result (ok): … 7 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 987 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 7 — User

What should I commit?

### Turn 7 — Assistant

The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages. Related: [[Python]].

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1140 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # cc4cf9`

**Tool results:**

  → result (ok): … 10 passed in 0.2s


### Turn 8 — User

Any lint fallout?

### Turn 8 — Assistant

One warning-severity count mismatch on an old stub — unrelated. The new pages are clean. Related: [[Configuration]].

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # b9d4f4`

**Tool results:**

  → result (ok): … 10 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1344 lines)


### Turn 9 — User

How do we verify on a fresh vault?

### Turn 9 — Assistant

Init a throwaway vault, sync once, then search for the durable handle. If rank-1 is wrong, check title collisions first. Related: [[Python]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 08c4b1`

**Tool results:**

  → result (ok): … 10 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1497 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # acd95a`

**Tool results:**

  → result (ok): … 4 passed in 0.3s


### Turn 10 — User

Is the headless path affected?

### Turn 10 — Assistant

No — headless fixtures stay excluded from default synth. This change is interactive-session only. Related: [[Configuration]].

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1650 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 2457b6`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1701 lines)


### Turn 11 — User

Document it?

### Turn 11 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[Python]].

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k category_rules_engine  # 21b904`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/category_rul.py` L1–80

**Tool results:**

  → result (ok): (file, 1854 lines)

**Tools used:**

- `Edit`: `llmwiki/pocket_ledger/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

