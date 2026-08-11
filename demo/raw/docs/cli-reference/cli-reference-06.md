---
title: "CLI reference (part 6/8: synthesize — deprecated alias for synth --sources-only)"
slug: cli-reference-06
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 6 of 8 of **CLI reference** — synthesize — deprecated alias for synth --sources-only.

## `synthesize` — deprecated alias for `synth --sources-only`

Kept so existing scripts do not break. Always prints a deprecation warning and defaults to sources-only (does **not** harvest candidates unless you pass `--candidates-only`). Prefer `llmwiki synth`.

```bash
python3 -m llmwiki synthesize --check
python3 -m llmwiki synthesize --estimate
python3 -m llmwiki synthesize --candidates-only   # still works; prefer synth
```

Same flags as [`synth`](#synth--synthesize-sources--harvest-candidates).

---

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

## `migrate-state` — one-time legacy state migration (v1.4.0)

Migrates legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-quarantine.json`, `.llmwiki-pending-prompts/`) into the unified `llmwiki-state.json`.

Implementation lives at `scripts/migrate_state_v1_4_0.py`; the CLI is a thin wrapper.

```bash
python3 scripts/migrate_state_v1_4_0.py
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
python3 -m llmwiki migrate-state
python3 -m llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
```

### Flags

| Flag | What |
|---|---|
| `--state-file PATH` | Explicit target state file (defaults to configured vault path). |
| `--json` | Print the migration report as JSON (script entry point only). |

The command is idempotent and prints cleanup suggestions for migrated legacy files.

It also repairs the vault (#23):

- **Legacy pending prompts are resolved, not re-queued.** Each `.llmwiki-pending-prompts/<uuid>.md` is matched against the pending sentinel pages (`<!-- llmwiki-pending: <uuid> -->`) still sitting in `wiki/sources/`. Prompts whose page has since been filled record nothing.
- **Dead `synth_request` items are purged.** The queue runner has no handler for that task type, so items left by an earlier migrator would fail forever. Re-running `migrate-state` removes them.
- **One `synthesize` task is enqueued** when — and only when — `synth.pending_total > 0` after the migration *and* no pending `synthesize` task is already queued, so re-running `migrate-state` never stacks duplicates. It drains the whole backlog; run it with `llmwiki queue run --vault <path>`.
- **Removed synthesis backends are flagged.** `synthesis.backend` values dropped in v1.4.0 (`agent`, `agent-delegate`, `agent_delegate`) silently fall back to `dummy`, which writes stub pages. The report prints a `WARNING:` telling you to set `claude`, `ollama`, or `dummy`.

Report keys: `state_file`, `migrated`, `orphan_cleanup_suggestions`, `warnings`, `pending_prompts_total`, `pending_prompts_unfilled`, `synth_request_items_purged`, `queued_synthesize`.

---

## `migrate-raw-redaction` — deterministic username rewrite in raw/ (#56)

Rewrites already-synced `raw/sessions/*.md` so home-path **and** dash-encoded agent-store segments use the `USER` placeholder (`-Users-<you>-…` → `-Users-USER-…`). In-place string rewrite only — does **not** re-convert from `~/.claude/projects` / Cursor stores, does **not** touch `wiki/`, and does **not** enqueue `synthesize`.

Prefer this over `llmwiki sync --force` when redaction completeness in existing `raw/` matters: agent transcripts are usually retained only ~30 days, so older sessions often have no source left to re-convert; force-sync followed by re-synth also burns LLM tokens for no benefit.

Implementation: `scripts/migrate_raw_encoded_username.py`; the CLI is a thin wrapper. After migrating, rebuild so `site/` picks up any display changes: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-raw-redaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-raw-redaction --vault /path/to/vault
python3 scripts/migrate_raw_encoded_username.py --vault /path/to/vault --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--real-username NAME` | Override `redaction.real_username` (default: config / `$USER`). |
| `--replacement-username NAME` | Override placeholder (default: `USER`). |

Idempotent: already-redacted files count as `unchanged`. Private local vaults that never publish `raw/` can skip this and only run `llmwiki build` after upgrading (see [UPGRADING.md](../UPGRADING.md)).

---

## `migrate-tools-used` — expand CallMcpTool frontmatter from origin stores

Rewrites `tools_used` and `tool_counts` in already-synced `raw/sessions/*.md` when the originating agent session file still exists. Re-reads records through the session adapter and applies the same `tool_use_recorded_names` expansion `llmwiki sync` uses (`CallMcpTool` → `mcp__{server}__{tool}`). In-place frontmatter update only — does **not** touch `wiki/`, does **not** enqueue `synthesize`, and **never** invents MCP names when the origin store is gone (TTL / deleted sessions count as `skipped_missing_origin` and stay unchanged).

Implementation: `scripts/migrate_tools_used_mcp.py`; the CLI is a thin wrapper. After migrating, rebuild so analytics and the site pick up the new tool names: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-tools-used --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-tools-used --vault /path/to/vault
python3 scripts/migrate_tools_used_mcp.py --vault /path/to/vault --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--config PATH` | Optional `sessions_config.json` override (record filters). |

Origin resolution prefers the vault's `llmwiki-state.json` sync keys (`adapter::home-relative-path`), then falls back to a glob under the adapter session store by `sessionId`. Claude Code JSONL is fully supported; Cursor and other non-JSONL stores work when the state key or glob resolves a readable origin path. Missing origins leave `CallMcpTool` entries intact for `wiki_adoption` body fallback.

---
