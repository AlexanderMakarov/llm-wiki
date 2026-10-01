---
title: "CLI reference (part 9/19: queue — inspect and run unified queue)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, queue-management, task-types, unified-queue, llmwiki-state]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This is CLI reference documentation for the `queue` command, which manages the unified task queue stored in `llmwiki-state.json`. The command provides three main operations: `status` (inspect queue state), `enqueue` (add new tasks), and `run` (execute pending tasks serially). Four task types are supported—add_doc, session_sync, synthesize, and build—each controlled via flags for source, vault path, and execution limits.

## Key Claims

- The unified queue is persisted in a file named `llmwiki-state.json` at a configurable path
- Four task types are supported: `add_doc`, `session_sync`, `synthesize`, and `build`
- Tasks are executed serially during a single `run` invocation, with a configurable per-call limit (default 20)
- The `status` subcommand displays queue depth, task-type breakdown, state file path, and the oldest pending task's timestamp

## Key Quotes

> "Manage the unified vault queue in `llmwiki-state.json`."
— Core purpose statement describing the queue command's role

> "Execute pending tasks serially (up to `--limit`)."
— Clarifies that task execution is sequential with a batch-size constraint

## Connections

- [[llmwiki]] (entity) — the queue command is a core CLI interface for task orchestration
  - fact: All queue operations are invoked via `python3 -m llmwiki queue` and manage state in the central state file
- [[Wiki Synthesis]] (concept) — `synthesize` is one of four supported task types in the queue
  - fact: Synthesis tasks can be enqueued and executed through the queue workflow