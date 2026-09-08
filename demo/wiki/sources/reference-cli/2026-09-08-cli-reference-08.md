---
title: "CLI reference (part 8/15: queue — inspect and run unified queue)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, unified-queue, llmwiki-state, vault-pipeline, add-doc, session-sync, vault-automation, headless-pipeline]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents `llmwiki queue`, which reads and updates the unified vault work queue stored in `llmwiki-state.json`. Operators can print status (counts, task-type breakdown, state path, oldest pending item), enqueue single tasks (`add_doc`, `session_sync`, `synthesize`, `build`), or run pending work serially with an optional `--limit` (default 20). Vault root and state file path are configurable via `--vault` and `--state-file`.

## Key Claims

- Queue state for the vault is centralized in `llmwiki-state.json`, overridable with `--state-file`.
- Supported enqueue task types are exactly `add_doc`, `session_sync`, `synthesize`, and `build`; `add_doc` requires `--source` (e.g. a URL).
- `queue run` processes pending tasks one at a time, stopping after `--limit` tasks (default 20) per invocation.
- Bare `python3 -m llmwiki queue` (or the `status` positional) reports queue counts, per-type breakdown, state path, and the oldest pending timestamp.

## Key Quotes

> "Manage the unified vault queue in `llmwiki-state.json`." — defines where queue persistence lives relative to the vault.

> "`run` | Execute pending tasks serially (up to `--limit`)." — execution model is serial, not parallel, per run.

## Connections

- [[llmwiki]] (entity) — host CLI; `queue` is the subcommand for inspect/enqueue/run on vault automation work.
  - fact: Queue integrates `add_doc`, `session_sync`, `synthesize`, and `build` into one state file.
- [[Wiki Synthesis]] (concept) — `synthesize` is a first-class queue task type, so batch runs can defer synthesis until `queue run`.
- [[Adapters]] (concept) — `session_sync` on the queue aligns with adapter-driven session ingestion without running sync immediately in the shell.
- [[Static Site]] (concept) — `build` as a queue task ties static site regeneration to the same unified pipeline as docs and sync.
