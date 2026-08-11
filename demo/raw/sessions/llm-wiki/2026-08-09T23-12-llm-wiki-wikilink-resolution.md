---
title: "Confirm how cross-references resolve before moving pages"
type: source
description: "Established that links resolve by filename, which decides whether a page can be relocated safely."
tags: [session]
date: 2026-08-09
source_file: raw/sessions/llm-wiki/2026-08-09T23-12-llm-wiki-wikilink-resolution.md
sessionId: d1f8e126-5997-f03a-2e0f-52dcb9cd6125
slug: wikilink-resolution
project: llm-wiki
started: 2026-08-09T23:12:00+00:00
ended: 2026-08-10T00:06:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: fix/wikilinks
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 11
tools_used: [Read, Grep, Bash]
tool_counts: {"Read": 5, "Grep": 8, "Bash": 4}
token_totals: {"input": 24120, "output": 4380}
turn_count: 4
duration_seconds: 3240
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 01644cff — 2026-08-09

Established that links resolve by filename, which decides whether a page can be relocated safely.

## Conversation

### Turn 1 — User

If I move a page from one folder to another, do links to it break?

### Turn 2 — Assistant

They do not. Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site.

So moving a page between folders is safe as long as the filename is unchanged. I added a test that moves a page and asserts the graph edge, the backlink and the lint result are all identical afterwards.

### Turn 3 — User

What about a page that was merged into another one?

### Turn 4 — Assistant

That is the case where links do break. Merging records the old name as an alias, but nothing consults aliases during resolution, so every existing reference to the merged-away name dangles.

## Subjects

- [[WikiLinks]]
- [[Knowledge Graph]]
- [[Lint Rules]]
