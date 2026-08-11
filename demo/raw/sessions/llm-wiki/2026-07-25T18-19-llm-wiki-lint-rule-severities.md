---
title: "Sort the lint rules into errors, warnings and information"
type: source
description: "Reviewed all seventeen rules and settled which ones should be able to fail a build."
tags: [session]
date: 2026-07-25
source_file: raw/sessions/llm-wiki/2026-07-25T18-19-llm-wiki-lint-rule-severities.md
sessionId: 6de52632-b146-448c-337c-2c29f84ff85a
slug: lint-rule-severities
project: llm-wiki
started: 2026-07-25T18:19:00+00:00
ended: 2026-07-25T18:40:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: chore/lint
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 25
tools_used: [Read, Grep, Bash]
tool_counts: {"Read": 8, "Grep": 4, "Bash": 7}
token_totals: {"input": 14990, "output": 2785}
turn_count: 4
duration_seconds: 1260
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: openclaw
---

# Session: 561a2466 — 2026-07-25

Reviewed all seventeen rules and settled which ones should be able to fail a build.

## Conversation

### Turn 1 — User

Lint reports everything at the same volume. Which of these should actually block a build?

### Turn 2 — Assistant

Went through all seventeen. Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere.

Nine are warnings — broken cross-references, stub pages, near-duplicate detection, tag conventions. They mean something is worth fixing but not that the output is wrong. The remaining four are informational, including orphan detection, which fires constantly on a young vault.

### Turn 3 — User

Freshness — error or warning?

### Turn 4 — Assistant

Warning, and arguably it should not fire at all on a fixed corpus. It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal.

## Subjects

- [[Lint Rules]]
- [[Static Site]]
- [[Frontmatter]]
- [[WikiLinks]]
