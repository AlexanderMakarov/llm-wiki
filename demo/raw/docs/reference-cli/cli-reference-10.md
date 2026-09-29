---
title: "CLI reference (part 10/19: migrate — list or apply a named one-time vault repair)"
slug: cli-reference-10
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 10 of 19 of **CLI reference** — migrate — list or apply a named one-time vault repair.

## `migrate` — list or apply a named one-time vault repair

Rare. One-time vault repairs after an upgrade — not part of the daily loop. List available migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing is applied until you choose a name: `llmwiki migrate <name> [flags]`. There is no run-everything default. Prefer `--dry-run` on a named migration to preview writes.

New migrations are registered under `migrate` in `llmwiki/cli.py`, not as new top-level commands. Older docs that said `migrate-X` mean `migrate <name>` (for example `migrate-raw-redaction` → `migrate raw-redaction`).

```bash
python3 -m llmwiki migrate
python3 -m llmwiki migrate --list
python3 -m llmwiki migrate state --state-file /path/to/vault/llmwiki-state.json
python3 -m llmwiki migrate raw-redaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate raw-unredaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate tools-used --vault /path/to/vault
python3 -m llmwiki migrate page-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate topic-kinds --vault /path/to/vault
python3 -m llmwiki migrate wikilink-titles --vault /path/to/vault --dry-run
python3 -m llmwiki migrate discarded-topic-links --vault /path/to/vault --dry-run
python3 -m llmwiki migrate source-page-paths --vault /path/to/vault --dry-run
python3 -m llmwiki migrate broken-provenance --vault /path/to/vault --dry-run
```

### `state` — one-time legacy state migration (v1.4.0)

Migrates legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-quarantine.json`, `.llmwiki-pending-prompts/`) into the unified `llmwiki-state.json`.

Implementation lives at `scripts/migrate_state_v1_4_0.py`; the CLI is a thin wrapper.

```bash
python3 -m llmwiki migrate state
python3 -m llmwiki migrate state --state-file /path/to/vault/llmwiki-state.json
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
```

| Flag | What |
|---|---|
| `--state-file PATH` | Explicit target state file (defaults to configured vault path). |

The command is idempotent and prints cleanup suggestions for migrated legacy files. It also repairs the vault: legacy pending prompts are resolved (not re-queued); dead `synth_request` queue items are purged; one `synthesize` queue task is enqueued when `synth.pending_total > 0` and none is already pending (drain with `llmwiki queue run --vault <path>`); removed synthesis backends (`agent`, `agent-delegate`, `agent_delegate`) print a `WARNING:` to set `claude`, `ollama`, or `dummy`. Report keys: `state_file`, `migrated`, `orphan_cleanup_suggestions`, `warnings`, `pending_prompts_total`, `pending_prompts_unfilled`, `synth_request_items_purged`, `queued_synthesize`.

### `raw-redaction` — deterministic username rewrite in raw/

Rewrites already-synced `raw/sessions/*.md` so home-path **and** dash-encoded agent-store segments use the `USER` placeholder (`-Users-<you>-…` → `-Users-USER-…`). In-place string rewrite only — does **not** re-convert from `~/.claude/projects` / Cursor stores, does **not** touch `wiki/`, and does **not** enqueue synthesis.

Prefer this over `llmwiki sync --force` when redaction completeness in existing `raw/` matters: agent transcripts are usually retained only ~30 days, so older sessions often have no source left to re-convert; force-sync followed by re-synth also burns LLM tokens for no benefit.

Implementation: `scripts/migrate_raw_encoded_username.py`. After migrating, rebuild so `site/` picks up any display changes: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate raw-redaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate raw-redaction --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--real-username NAME` | Override `redaction.real_username` (default: config / `$USER`). |
| `--replacement-username NAME` | Override placeholder (default: `USER`). |

Runs regardless of `redaction.redact_username` — invoking it is the explicit request to redact. Idempotent: already-redacted files count as `unchanged`. Private local vaults that never publish `raw/` can skip this and only run `llmwiki build` after upgrading (see [UPGRADING.md](../UPGRADING.md)).

### `raw-unredaction` — restore real usernames in raw/ paths

Reverse of `raw-redaction` (#253). Rewrites already-synced `raw/sessions/*.md` so the `USER` placeholder in home-path and dash-encoded segments (`/home/USER/…`, `-Users-USER-…`) becomes your real username again. A bare `USER` word outside a path position is never touched. Same file scope and guarantees as `raw-redaction`: no re-convert, no `wiki/` changes, no synthesis.

Use it on a private vault synced while `redaction.redact_username` was on (the default before #253). Refuses (exit 2) when the real username is empty or equals the placeholder. Prints a note when the effective config still has `redaction.redact_username: true`, since new syncs would write the placeholder again. Rebuild afterwards: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate raw-unredaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate raw-unredaction --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--real-username NAME` | Username to restore (default: `redaction.real_username` / `$USER`). |
| `--replacement-username NAME` | Placeholder to replace (default: `USER`). |

Idempotent: files with no placeholder left count as `unchanged`.

Limitations — review the `--dry-run` list before writing:

- It cannot tell a redacted path from a placeholder path a person typed on purpose. Prose that quotes a rule such as "use `/home/USER/…`" is rewritten to your real home path too.
- It restores one target username for every file. In a vault synced from several machines or accounts, that name is wrong for files that came from the others.

### `tools-used` — expand CallMcpTool frontmatter from origin stores

Rewrites `tools_used` and `tool_counts` in already-synced `raw/sessions/*.md` when the originating agent session file still exists. Re-reads records through the session adapter and applies the same `tool_use_recorded_names` expansion `llmwiki sync` uses (`CallMcpTool` → `mcp__{server}__{tool}`). In-place frontmatter update only — does **not** touch `wiki/`, does **not** enqueue synthesis, and **never** invents MCP names when the origin store is gone (TTL / deleted sessions count as `skipped_missing_origin` and stay unchanged).

Implementation: `scripts/migrate_tools_used_mcp.py`. After migrating, rebuild so analytics and the site pick up the new tool names: `llmwiki build --vault PATH`.
