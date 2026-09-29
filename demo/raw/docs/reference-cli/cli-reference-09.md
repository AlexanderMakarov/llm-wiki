---
title: "CLI reference (part 9/19: queue — inspect and run unified queue)"
slug: cli-reference-09
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 9 of 19 of **CLI reference** — queue — inspect and run unified queue.

## `queue` — inspect and run unified queue

Manage the unified vault queue in `llmwiki-state.json`.

```bash
python3 -m llmwiki queue
python3 -m llmwiki queue enqueue --task-type add_doc --source https://example.com
python3 -m llmwiki queue run --vault /path/to/vault --limit 20
```

### Positional

| Value | What |
|---|---|
| `status` | Print queue counts, task-type breakdown, state path, and oldest pending timestamp. |
| `enqueue` | Add one task (`add_doc`, `session_sync`, `synthesize`, `build`). |
| `run` | Execute pending tasks serially (up to `--limit`). |

### Flags

| Flag | What |
|---|---|
| `--task-type {add_doc,session_sync,synthesize,build}` | Task kind for `enqueue`. |
| `--source TEXT` | Source payload for `add_doc` enqueue. |
| `--limit N` | Max tasks to process in one `run` call. Default: `20`. |
| `--vault PATH` | Vault root used for task execution and state lookup. |
| `--state-file PATH` | Override direct state file path. |

---
