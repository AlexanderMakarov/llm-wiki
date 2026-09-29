---
title: "CLI reference (part 9/19: queue — inspect and run unified queue)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, queue, task-scheduling, state-file]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

Reference documentation for the `queue` command, which manages llmwiki's unified task queue persisted in `llmwiki-state.json`. Describes operations to enqueue tasks (add_doc, session_sync, synthesize, build), check queue status, and execute pending tasks serially with a configurable limit.

## Key Claims

- The queue command manages a unified vault queue stored in `llmwiki-state.json`
- Four task types are supported: `add_doc`, `session_sync`, `synthesize`, and `build`
- Tasks are executed serially during `run` operations with a default limit of 20 tasks per invocation
- Queue status displays task counts by type, the state file path, and the timestamp of the oldest pending task
- The `--vault` flag specifies which vault's queue to operate on; `--state-file` overrides the default state file location

## Key Quotes

> "Manage the unified vault queue in `llmwiki-state.json`." — establishes persistent state management as the foundation of the queue system

> "Execute pending tasks serially (up to `--limit`)" — indicates sequential execution rather than parallel processing, with a configurable upper bound per invocation

## Connections

- [[llmwiki]] (entity) — the command-line tool whose queue subsystem is documented here
  - fact: The `queue` command is a core CLI interface for managing task orchestration across vault operations
- [[Wiki Synthesis]] (concept) — wiki building is one of the four supported queue task types
  - fact: Tasks can trigger wiki synthesis operations via the `synthesize` task type
- [[Adapters]] (entity) — document ingestion pipeline that is triggered via the queue
  - fact: The `add_doc` task type enqueues document ingestion, enabling programmatic adapter-driven ingestion

## Contradictions

None identified.