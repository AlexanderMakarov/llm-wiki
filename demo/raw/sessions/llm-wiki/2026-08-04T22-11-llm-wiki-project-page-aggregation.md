---
title: "Seed project pages from session metadata"
type: source
description: "Project pages are now derived from session frontmatter rather than written by hand."
tags: [session]
date: 2026-08-04
source_file: raw/sessions/llm-wiki/2026-08-04T22-11-llm-wiki-project-page-aggregation.md
sessionId: 2ed9df4c-893c-6f6c-2bc4-d1d5c2988185
slug: project-page-aggregation
project: llm-wiki
started: 2026-08-04T22:11:00+00:00
ended: 2026-08-04T23:00:00+00:00
cwd: /home/USER/code/llm-wiki
gitBranch: feat/projects
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 22
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 5, "Edit": 8, "Bash": 4}
token_totals: {"input": 18310, "output": 3365}
turn_count: 4
duration_seconds: 2940
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: cursor-cli
---

# Session: ab6adcee — 2026-08-04

Project pages are now derived from session frontmatter rather than written by hand.

## Conversation

### Turn 1 — User

Project pages are stale — I have to edit them whenever I add sessions.

### Turn 2 — Assistant

They are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists.

One consequence worth knowing: those stubs carry no last-updated date of their own. A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it.

### Turn 3 — User

What if two clones of the same repo produce different project names?

### Turn 4 — Assistant

They currently produce two projects. The name comes from the working directory, so a second clone reads as separate work. Worth solving, but it needs a stable project identity rather than a path.

## Subjects

- [[Session Metadata]]
- [[Frontmatter]]
- [[Static Site]]
