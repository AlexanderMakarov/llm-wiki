---
title: "Make the built site work without a server or a network"
type: source
description: "Vendored the graph library and moved state into a script tag so the site opens from a file."
tags: [session-transcript, session]
date: 2026-08-29
source_file: raw/sessions/llm-wiki/2026-08-29T20-45-llm-wiki-static-site-offline.md
sessionId: 1dab43b8-145a-b03e-493a-2b2d1f3ccb04
slug: static-site-offline
project: llm-wiki
started: 2026-08-29T20:45:00+00:00
ended: 2026-08-30T00:22:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/offline
permissionMode: default
model: claude-opus-5
user_messages: 15
tool_calls: 48
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 16, "Edit": 16, "Bash": 16}
token_totals: {"input": 20660, "output": 4580}
turn_count: 15
duration_seconds: 13020
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 00503fd4 — 2026-08-29

**Project:** `llm-wiki` · **Branch:** `feat/offline` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 15 user messages, 48 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

Can I just open the site from disk, or do I need to serve it? Call out plixbuffer explicitly in the notes — it is the durable handle we want search to recover later.

### Turn 1 — Assistant

You can now. Two things were in the way. The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence.

The bigger one: page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk.

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # bd526f`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 2 — User

What still needs a server?

### Turn 2 — Assistant

Only the candidates page, which posts review decisions to a small endpoint. Everything else — home, projects, sessions, topics, search, graph — is static.

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 92893c`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)


### Turn 3 — User

Document it?

### Turn 3 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[Deployment]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 3eafa8`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 477 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 4 — User

Ship it?

### Turn 4 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 630 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # f7dd0f`

**Tool results:**

  → result (ok): … 7 passed in 0.2s


### Turn 5 — User

Does that cover the edge case we hit last week?

### Turn 5 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Knowledge Graph]].

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # fa4246`

**Tool results:**

  → result (ok): … 7 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 834 lines)


### Turn 6 — User

Can you show the command you ran?

### Turn 6 — Assistant

Listed below in the tool trace. The interesting bit is the exit code and the first matching line. Related: [[Deployment]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 32ca11`

**Tool results:**

  → result (ok): … 7 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 987 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 7 — User

What should I commit?

### Turn 7 — Assistant

The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 1140 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # a68bd6`

**Tool results:**

  → result (ok): … 10 passed in 0.2s


### Turn 8 — User

Any lint fallout?

### Turn 8 — Assistant

One warning-severity count mismatch on an old stub — unrelated. The new pages are clean. Related: [[Knowledge Graph]].

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 9df978`

**Tool results:**

  → result (ok): … 10 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 1344 lines)


### Turn 9 — User

How do we verify on a fresh vault?

### Turn 9 — Assistant

Init a throwaway vault, sync once, then search for the durable handle. If rank-1 is wrong, check title collisions first. Related: [[Deployment]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 7d6080`

**Tool results:**

  → result (ok): … 10 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 1497 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 10 — User

Is the headless path affected?

### Turn 10 — Assistant

No — headless fixtures stay excluded from default synth. This change is interactive-session only. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 1650 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 9235da`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 11 — User

Document it?

### Turn 11 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[Knowledge Graph]].

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # c08d95`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 1854 lines)


### Turn 12 — User

Ship it?

### Turn 12 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Deployment]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 7cd824`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 2007 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 13 — User

Does that cover the edge case we hit last week?

### Turn 13 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 2160 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 8e95fd`

**Tool results:**

  → result (ok): … 7 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 2211 lines)


### Turn 14 — User

Can you show the command you ran?

### Turn 14 — Assistant

Listed below in the tool trace. The interesting bit is the exit code and the first matching line. Related: [[Knowledge Graph]].

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 582a03`

**Tool results:**

  → result (ok): … 7 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 2364 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 15 — User

What should I commit?

### Turn 15 — Assistant

The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages. Related: [[Deployment]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 457ccd`

**Tool results:**

  → result (ok): … 7 passed in 0.0s

**Tools used:**

- `Read`: `llmwiki/static_site_.py` L1–80

**Tool results:**

  → result (ok): (file, 2517 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k static_site_offline  # 43d533`

**Tool results:**

  → result (ok): … 10 passed in 0.3s

