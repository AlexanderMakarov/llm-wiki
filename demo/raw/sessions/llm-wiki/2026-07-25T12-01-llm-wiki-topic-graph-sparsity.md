---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
description: "A two-node topic graph rendered as an empty-looking viewer, so the build now falls back when topics are sparse."
tags: [session-transcript, session]
date: 2026-07-25
source_file: raw/sessions/llm-wiki/2026-07-25T12-01-llm-wiki-topic-graph-sparsity.md
sessionId: df12fe76-205b-d838-fdf1-c146d7b60662
slug: topic-graph-sparsity
project: llm-wiki
started: 2026-07-25T12:01:00+00:00
ended: 2026-07-25T15:33:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/graph
permissionMode: default
model: claude-opus-5
user_messages: 15
tool_calls: 49
tools_used: [Read, Edit, Bash, Glob]
tool_counts: {"Read": 15, "Edit": 9, "Bash": 16, "Glob": 9}
token_totals: {"input": 20460, "output": 4615}
turn_count: 15
duration_seconds: 12720
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: d4ea3993 — 2026-07-25

**Project:** `llm-wiki` · **Branch:** `feat/graph` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 15 user messages, 49 tool calls, tools used: Read, Edit, Bash, Glob.

## Conversation

### Turn 1 — User

The graph page looks broken on a small vault — one edge and two nodes floating in space.

### Turn 1 — Assistant

That is the topic graph with almost nothing in it. Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small.

I added a threshold: below five topics the build falls back to the full page graph, which always has content because every page is a node. The build prints which graph it chose and why, so the fallback is visible rather than mysterious.

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # d982f2`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 2 — User

Does the fallback change the topic pages?

### Turn 2 — Assistant

Yes — topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output. It is a real limitation of a small vault rather than something to paper over.

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # f2b67a`

**Tool results:**

  → result (ok): … 3 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (9eec01)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)


### Turn 3 — User

Is the headless path affected?

### Turn 3 — Assistant

No — headless fixtures stay excluded from default synth. This change is interactive-session only. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 460 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # f226ec`

**Tool results:**

  → result (ok): … 6 passed in 0.2s


### Turn 4 — User

Document it?

### Turn 4 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[WikiLinks]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 14be33`

**Tool results:**

  → result (ok): … 5 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (eb1f71)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 664 lines)


### Turn 5 — User

Ship it?

### Turn 5 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Knowledge Graph]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 800 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 616fa1`

**Tool results:**

  → result (ok): … 8 passed in 0.2s


### Turn 6 — User

Does that cover the edge case we hit last week?

### Turn 6 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Topic Pages]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 10af39`

**Tool results:**

  → result (ok): … 7 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (8997f4)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1004 lines)


### Turn 7 — User

Can you show the command you ran?

### Turn 7 — Assistant

Listed below in the tool trace. The interesting bit is the exit code and the first matching line. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1140 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # f1a558`

**Tool results:**

  → result (ok): … 10 passed in 0.2s


### Turn 8 — User

What should I commit?

### Turn 8 — Assistant

The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages. Related: [[WikiLinks]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 915ffc`

**Tool results:**

  → result (ok): … 9 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (10ad3d)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1344 lines)


### Turn 9 — User

Any lint fallout?

### Turn 9 — Assistant

One warning-severity count mismatch on an old stub — unrelated. The new pages are clean. Related: [[Knowledge Graph]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1480 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 26acdb`

**Tool results:**

  → result (ok): … 3 passed in 0.2s


### Turn 10 — User

How do we verify on a fresh vault?

### Turn 10 — Assistant

Init a throwaway vault, sync once, then search for the durable handle. If rank-1 is wrong, check title collisions first. Related: [[Topic Pages]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 5474d2`

**Tool results:**

  → result (ok): … 2 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (9c306e)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1684 lines)


### Turn 11 — User

Is the headless path affected?

### Turn 11 — Assistant

No — headless fixtures stay excluded from default synth. This change is interactive-session only. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 1820 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 5ed66c`

**Tool results:**

  → result (ok): … 5 passed in 0.2s


### Turn 12 — User

Document it?

### Turn 12 — Assistant

A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag. Related: [[WikiLinks]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # 1e6e05`

**Tool results:**

  → result (ok): … 4 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (e2bd05)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 2024 lines)


### Turn 13 — User

Ship it?

### Turn 13 — Assistant

After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR. Related: [[Knowledge Graph]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 2160 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # ba9bd5`

**Tool results:**

  → result (ok): … 7 passed in 0.2s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (067802)


### Turn 14 — User

Does that cover the edge case we hit last week?

### Turn 14 — Assistant

Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it. Related: [[Topic Pages]].

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # a91204`

**Tool results:**

  → result (ok): … 6 passed in 0.0s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (91a4c7)

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 2364 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 15 — User

Can you show the command you ran?

### Turn 15 — Assistant

Listed below in the tool trace. The interesting bit is the exit code and the first matching line. Related: [[Static Site]].

**Tools used:**

- `Read`: `llmwiki/topic_graph_.py` L1–80

**Tool results:**

  → result (ok): (file, 2500 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k topic_graph_sparsity  # e6f42f`

**Tool results:**

  → result (ok): … 9 passed in 0.2s

**Tools used:**

- `Glob`: `llm-wiki/topic-graph-sparsity`

**Tool results:**

  → result (ok): ok (d4866a)

**Tools used:**

- `Bash`: `llmwiki search --mode phrase 'ovrix delta plan'`

**Tool results:**

  → result (ok): 1. wiki/sources/… — score 12.4 (phrase hit on ovrix delta plan)

