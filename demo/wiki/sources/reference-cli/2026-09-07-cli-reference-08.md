---
title: "CLI reference (part 8/15: queue — inspect and run unified queue)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, queue-command, task-enqueue, task-execution, state-file]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-08.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This document specifies the `queue` CLI subcommand, which manages a unified task queue stored in `llmwiki-state.json`. The command provides three main operations: inspecting queue status, enqueuing new tasks (add_doc, session_sync, synthesize, build), and executing pending tasks with configurable limits. Part 8 of the 15-part CLI reference series.

## Key Claims

- The unified queue is persisted in a file called `llmwiki-state.json`
- Queue supports four task types: `add_doc`, `session_sync`, `synthesize`, and `build`
- The `status` subcommand displays queue counts, task-type breakdown, state file path, and the oldest pending task's timestamp
- The `run` subcommand executes pending tasks serially with a default limit of 20 tasks per invocation
- Queue state can be overridden via `--state-file` flag, bypassing the default state file lookup

## Key Quotes

> "Manage the unified vault queue in `llmwiki-state.json`" — establishes the central state storage mechanism for the queue system

> "Execute pending tasks serially (up to `--limit`). Default: `20`." — defines the default concurrency model and batch size for task execution

## Connections

- [[llmwiki]] (project) — the queue command is a core subsystem for task management within the personal wiki system
- [[Configuration Reference]] (concept) — documents how to configure queue behavior and state file locations
- [[Codex CLI]] (tool) — queue is a major subcommand in the CLI toolset