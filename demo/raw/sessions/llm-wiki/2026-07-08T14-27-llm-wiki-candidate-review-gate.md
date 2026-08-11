---
title: "Add the candidate review gate between harvest and promotion"
type: source
description: "Harvest now writes stubs to a review folder instead of publishing pages directly."
tags: [session]
date: 2026-07-08
source_file: raw/sessions/llm-wiki/2026-07-08T14-27-llm-wiki-candidate-review-gate.md
sessionId: 8ad5cabb-b9c8-c2af-fcac-882c1a39c85e
slug: candidate-review-gate
project: llm-wiki
started: 2026-07-08T14:27:00+00:00
ended: 2026-07-08T15:04:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/candidates
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 28
tools_used: [Read, Edit, Bash, Grep]
tool_counts: {"Read": 4, "Edit": 7, "Bash": 3, "Grep": 6}
token_totals: {"input": 11670, "output": 2205}
turn_count: 4
duration_seconds: 2220
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: adc0ae00 — 2026-07-08

Harvest now writes stubs to a review folder instead of publishing pages directly.

## Conversation

### Turn 1 — User

Harvest is writing entity pages straight into the wiki. I want to review them first.

### Turn 2 — Assistant

Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted.

Review happens through `llmwiki candidates`: list, promote, flip-promote when the kind is wrong, merge when two stubs describe the same subject, discard with a reason. Discards are archived rather than deleted so the decision is recoverable.

### Turn 3 — User

What decides whether something becomes a candidate at all?

### Turn 4 — Assistant

The number of distinct source pages naming it. Default is three; `--min-refs` lowers it. A subject mentioned once is usually incidental, and promoting it produces a page with a single fact on it.

## Subjects

- [[Candidate Review]]
- [[Wiki Synthesis]]
- [[WikiLinks]]
- [[Frontmatter]]
