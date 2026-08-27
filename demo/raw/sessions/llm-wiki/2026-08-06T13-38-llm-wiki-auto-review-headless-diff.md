---
title: "Auto-review headless pass on a synthetic diff"
type: source
description: "Synthetic Cursor Agent CLI auto-review launch; headless via approvalMode."
tags: [cursor-cli, session]
date: 2026-08-06
source_file: raw/sessions/llm-wiki/2026-08-06T13-38-llm-wiki-auto-review-headless-diff.md
sessionId: 51638fbe-4685-04c3-5d54-d7c213c54429
slug: auto-review-headless-diff
project: llm-wiki
started: 2026-08-06T13:38:00+00:00
ended: 2026-08-06T14:02:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: chore/headless-demo
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 21
tools_used: [Read, Grep, Bash]
tool_counts: {"Read": 7, "Grep": 3, "Bash": 6}
token_totals: {"input": 25780, "output": 4670}
turn_count: 4
duration_seconds: 1440
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: true
approvalMode: auto-review
agent: cursor-cli
---

# Session: 4633a76e — 2026-08-06

Synthetic Cursor Agent CLI auto-review launch; headless via approvalMode.

## Conversation

### Turn 1 — User

Review the synthetic patch for frontmatter and link issues only.

### Turn 2 — Assistant

Checked the fixture diff. No broken wikilinks; one frontmatter date disagrees with the filename stamp and is noted as a warning.

Authored for the demo corpus — no real user vault content.

### Turn 3 — User

Is that enough to block merge under the demo policy?

### Turn 4 — Assistant

Under errors-only, no. Under fail-on-warnings, yes. The demo policy matches the product default of reporting without failing a scheduled job.

## Subjects

- [[Lint Rules]]
- [[Static Site]]
- [[Frontmatter]]
