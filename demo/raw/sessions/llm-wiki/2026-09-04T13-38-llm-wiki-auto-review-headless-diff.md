---
title: "Auto-review headless pass on a synthetic diff"
type: source
description: "Synthetic Cursor Agent CLI auto-review launch; headless via approvalMode."
tags: [session-transcript, cursor-cli, session]
date: 2026-09-04
source_file: raw/sessions/llm-wiki/2026-09-04T13-38-llm-wiki-auto-review-headless-diff.md
sessionId: 51638fbe-4685-04c3-5d54-d7c213c54429
slug: auto-review-headless-diff
project: llm-wiki
started: 2026-09-04T13:38:00+00:00
ended: 2026-09-04T14:19:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: chore/headless-demo
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 6
tools_used: [Read, Grep, Bash]
tool_counts: {"Read": 2, "Grep": 2, "Bash": 2}
token_totals: {"input": 4360, "output": 770}
turn_count: 2
duration_seconds: 2460
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: true
approvalMode: auto-review
agent: cursor-cli
---

# Session: 4633a76e — 2026-09-04

**Project:** `llm-wiki` · **Branch:** `chore/headless-demo` · **Mode:** `default` · **Model:** `claude-opus-5`

**Stats:** 2 user messages, 6 tool calls, tools used: Read, Grep, Bash.

## Conversation

### Turn 1 — User

Review the synthetic patch for frontmatter and link issues only.

### Turn 1 — Assistant

Checked the fixture diff. No broken wikilinks; one frontmatter date disagrees with the filename stamp and is noted as a warning.

Authored for the demo corpus — no real user vault content.

**Tools used:**

- `Read`: `llmwiki/auto_review_.py` L1–80

**Tool results:**

  → result (ok): (file, 120 lines)

**Tools used:**

- `Grep`: pattern `auto-review-headless-diff` path `llmwiki/`

**Tool results:**

  → result (ok): llmwiki/cli.py:11: …

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k auto_review_headless_diff  # 94af78`

**Tool results:**

  → result (ok): … 4 passed in 0.2s


### Turn 2 — User

Is that enough to block merge under the demo policy?

### Turn 2 — Assistant

Under errors-only, no. Under fail-on-warnings, yes. The demo policy matches the product default of reporting without failing a scheduled job.

**Tools used:**

- `Grep`: pattern `auto-review-headless-diff` path `llmwiki/`

**Tool results:**

  → result (ok): llmwiki/cli.py:20: …

**Tools used:**

- `Bash`: `python3 -m pytest tests/ -q -k auto_review_headless_diff  # 511d78`

**Tool results:**

  → result (ok): … 4 passed in 0.1s

**Tools used:**

- `Read`: `llmwiki/auto_review_.py` L1–80

**Tool results:**

  → result (ok): (file, 324 lines)

Connections: [[Lint Rules]], [[Static Site]], [[Frontmatter]].
