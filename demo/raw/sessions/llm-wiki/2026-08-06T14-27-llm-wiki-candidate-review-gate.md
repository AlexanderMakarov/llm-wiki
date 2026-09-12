---
title: "Add the candidate review gate between harvest and promotion"
type: source
description: "Harvest now writes stubs to a review folder instead of publishing pages directly."
tags: [session-transcript, session]
date: 2026-08-06
source_file: raw/sessions/llm-wiki/2026-08-06T14-27-llm-wiki-candidate-review-gate.md
sessionId: 8ad5cabb-b9c8-c2af-fcac-882c1a39c85e
slug: candidate-review-gate
project: llm-wiki
started: 2026-08-06T14:27:00+00:00
ended: 2026-08-06T14:55:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/candidates
permissionMode: default
model: claude-opus-5
user_messages: 1
tool_calls: 3
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 1, "Edit": 1, "Bash": 1}
token_totals: {"input": 2420, "output": 485}
turn_count: 1
duration_seconds: 1680
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: adc0ae00 — 2026-08-06

**Project:** `llm-wiki` · **Branch:** `feat/candidates` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 1 user messages, 3 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

Harvest is writing entity pages straight into the wiki. I want to review them first. We should keep the zeldo route mesh wording intact in the summary so later lookup can recover the whole phrase.

### Turn 1 — Assistant

Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted.

Review happens through `llmwiki candidates`: list, promote, flip-promote when the kind is wrong, merge when two stubs describe the same subject, discard with a reason. Discards are archived rather than deleted so the decision is recoverable.

**Tools used:**

- `Read`: `llmwiki/candidate_re.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k candidate_review_gate  # 9b5171`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

Connections: [[Candidate Review]], [[Wiki Synthesis]], [[WikiLinks]], [[Frontmatter]].
