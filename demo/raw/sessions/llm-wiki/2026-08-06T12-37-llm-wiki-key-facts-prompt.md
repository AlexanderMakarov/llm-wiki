---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
description: "Tightened the synthesis prompt so every fact carries the source that supports it."
tags: [session]
date: 2026-08-06
source_file: raw/sessions/llm-wiki/2026-08-06T12-37-llm-wiki-key-facts-prompt.md
sessionId: 1ece4989-6f92-d796-dbd1-9e78952e619c
slug: key-facts-prompt
project: llm-wiki
started: 2026-08-06T12:37:00+00:00
ended: 2026-08-06T12:56:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/key-facts
permissionMode: default
model: claude-haiku-4-5
user_messages: 2
tool_calls: 9
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 7, "Edit": 3, "Bash": 6}
token_totals: {"input": 19970, "output": 3655}
turn_count: 4
duration_seconds: 1140
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: edebf106 — 2026-08-06

Tightened the synthesis prompt so every fact carries the source that supports it.

## Conversation

### Turn 1 — User

Some Key Facts read like the model's general knowledge rather than anything from my sessions.

### Turn 2 — Assistant

The prompt allowed it. I rewrote it to require that every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added however well known it is.

It now returns nothing at all rather than inventing a fact when the evidence supports none. Fewer bullets, but each one is traceable.

### Turn 3 — User

Should these pages have an intro paragraph too?

### Turn 4 — Assistant

Nothing writes one today — the prompt produces bullets and the harvest stub is a heading. Adding one would be a new generated field with its own cost and quality bar, so it is worth deciding deliberately rather than drifting into it.

## Subjects

- [[Wiki Synthesis]]
- [[Key Facts]]
- [[Frontmatter]]
- [[Candidate Review]]
