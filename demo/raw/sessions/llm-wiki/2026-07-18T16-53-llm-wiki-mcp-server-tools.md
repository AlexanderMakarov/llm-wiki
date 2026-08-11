---
title: "Expose the wiki over MCP so any agent can read it"
type: source
description: "Added search, read-page and query tools to the MCP server and pinned the kind vocabulary to one source."
tags: [session]
date: 2026-07-18
source_file: raw/sessions/llm-wiki/2026-07-18T16-53-llm-wiki-mcp-server-tools.md
sessionId: 18c5a016-ac9e-22c2-61cc-eab3419c6934
slug: mcp-server-tools
project: llm-wiki
started: 2026-07-18T16:53:00+00:00
ended: 2026-07-18T17:44:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/mcp
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 15
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 6, "Edit": 2, "Bash": 5}
token_totals: {"input": 13330, "output": 2495}
turn_count: 4
duration_seconds: 3060
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 912b2361 — 2026-07-18

Added search, read-page and query tools to the MCP server and pinned the kind vocabulary to one source.

## Conversation

### Turn 1 — User

I want Cursor to be able to read the wiki without me pasting anything.

### Turn 2 — Assistant

The MCP server already exposed a search tool. I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph.

One thing worth noting: the tool schema advertises the page kinds a caller can filter by, and that list was hardcoded separately from the schema module. I pointed both at the same constant so they cannot drift.

### Turn 3 — User

Does it work from Cursor specifically?

### Turn 4 — Assistant

Yes — it is a stdio server, so any MCP client can launch it. Cursor, Claude Code and Codex CLI all connect the same way. The server is a consumer surface and is entirely separate from the adapters that read session stores.

## Subjects

- [[MCP Server]]
- [[Claude Code]]
- [[Cursor]]
- [[Frontmatter]]
