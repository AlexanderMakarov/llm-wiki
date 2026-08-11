---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
description: "A two-node topic graph rendered as an empty-looking viewer, so the build now falls back when topics are sparse."
tags: [session]
date: 2026-06-26
source_file: raw/sessions/llm-wiki/2026-06-26T12-01-llm-wiki-topic-graph-sparsity.md
sessionId: df12fe76-205b-d838-fdf1-c146d7b60662
slug: topic-graph-sparsity
project: llm-wiki
started: 2026-06-26T12:01:00+00:00
ended: 2026-06-26T12:24:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/graph
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 18
tools_used: [Read, Edit, Bash, Glob]
tool_counts: {"Read": 2, "Edit": 5, "Bash": 8, "Glob": 4}
token_totals: {"input": 10010, "output": 1915}
turn_count: 4
duration_seconds: 1380
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: d4ea3993 — 2026-06-26

A two-node topic graph rendered as an empty-looking viewer, so the build now falls back when topics are sparse.

## Conversation

### Turn 1 — User

The graph page looks broken on a small vault — one edge and two nodes floating in space.

### Turn 2 — Assistant

That is the topic graph with almost nothing in it. Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small.

I added a threshold: below five topics the build falls back to the full page graph, which always has content because every page is a node. The build prints which graph it chose and why, so the fallback is visible rather than mysterious.

### Turn 3 — User

Does the fallback change the topic pages?

### Turn 4 — Assistant

Yes — topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output. It is a real limitation of a small vault rather than something to paper over.

## Subjects

- [[Knowledge Graph]]
- [[Topic Pages]]
- [[Static Site]]
- [[WikiLinks]]
