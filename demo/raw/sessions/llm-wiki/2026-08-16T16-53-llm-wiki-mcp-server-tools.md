---
title: "Expose the wiki over MCP so any agent can read it"
type: source
description: "Added search, read-page and query tools to the MCP server and pinned the kind vocabulary to one source."
tags: [session-transcript, session]
date: 2026-08-16
source_file: raw/sessions/llm-wiki/2026-08-16T16-53-llm-wiki-mcp-server-tools.md
sessionId: 18c5a016-ac9e-22c2-61cc-eab3419c6934
slug: mcp-server-tools
project: llm-wiki
started: 2026-08-16T16:53:00+00:00
ended: 2026-08-16T17:50:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/mcp
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 11
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 3, "Edit": 4, "Bash": 4}
token_totals: {"input": 4360, "output": 945}
turn_count: 2
duration_seconds: 3420
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: 912b2361 — 2026-08-16

**Project:** `llm-wiki` · **Branch:** `feat/mcp` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 2 user messages, 11 tool calls, tools used: Read, Edit, Bash.

## Conversation

### Turn 1 — User

I want Cursor to be able to read the wiki without me pasting anything.

### Turn 1 — Assistant

The MCP server already exposed a search tool. I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph.

One thing worth noting: the tool schema advertises the page kinds a caller can filter by, and that list was hardcoded separately from the schema module. I pointed both at the same constant so they cannot drift.

**Tools used:**

- `Read`: `llmwiki/mcp_server_t.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k mcp_server_tools  # 4e586f`

**Tool results:**

  → result (ok): … 4 passed in 0.2s

**Tools used:**

- `Read`: `llmwiki/mcp_server_t.py` L1–80

**Tool results:**

  → result (ok): (file, 171 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk


### Turn 2 — User

Does it work from Cursor specifically?

### Turn 2 — Assistant

Yes — it is a stdio server, so any MCP client can launch it. Cursor, Claude Code and Codex CLI all connect the same way. The server is a consumer surface and is entirely separate from the adapters that read session stores.

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k mcp_server_tools  # fc0dac`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/mcp_server_t.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

**Tools used:**

- `Edit`: `llmwiki/llm_wiki/handler.py`

**Tool results:**

  → result (ok): ok — 1 hunk

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k mcp_server_tools  # 3d195e`

**Tool results:**

  → result (ok): … 7 passed in 0.4s

**Tools used:**

- `Bash`: `rg -n glypherun wiki/`

**Tool results:**

  → result (ok): wiki/overview.md:14: … glypherun …

Connections: [[MCP Server]], [[Claude Code]], [[Cursor]], [[Frontmatter]].
