---
title: "CLI reference (part 9/15: migrate — list or apply a named one-time vault repair)"
slug: cli-reference-09
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 9 of 15 of **CLI reference** — migrate — list or apply a named one-time vault repair.

## `migrate` — list or apply a named one-time vault repair

Rare. One-time vault repairs after an upgrade — not part of the daily loop. List available migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing is applied until you choose a name: `llmwiki migrate <name> [flags]`. There is no run-everything default. Prefer `--dry-run` on a named migration to preview writes.

New migrations are registered under `migrate` in `llmwiki/cli.py`, not as new top-level commands. Older docs that said `migrate-X` mean `migrate <name>` (for example `migrate-raw-redaction` → `migrate raw-redaction`).

```bash
python3 -m llmwiki migrate
python3 -m llmwiki migrate --list
python3 -m llmwiki migrate state --state-file /path/to/vault/llmwiki-state.json
python3 -m llmwiki migrate raw-redaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate tools-used --vault /path/to/vault
python3 -m llmwiki migrate page-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate topic-kinds --vault /path/to/vault
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

Idempotent: already-redacted files count as `unchanged`. Private local vaults that never publish `raw/` can skip this and only run `llmwiki build` after upgrading (see [UPGRADING.md](../UPGRADING.md)).

### `tools-used` — expand CallMcpTool frontmatter from origin stores

Rewrites `tools_used` and `tool_counts` in already-synced `raw/sessions/*.md` when the originating agent session file still exists. Re-reads records through the session adapter and applies the same `tool_use_recorded_names` expansion `llmwiki sync` uses (`CallMcpTool` → `mcp__{server}__{tool}`). In-place frontmatter update only — does **not** touch `wiki/`, does **not** enqueue synthesis, and **never** invents MCP names when the origin store is gone (TTL / deleted sessions count as `skipped_missing_origin` and stay unchanged).

Implementation: `scripts/migrate_tools_used_mcp.py`. After migrating, rebuild so analytics and the site pick up the new tool names: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate tools-used --vault /path/to/vault --dry-run
python3 -m llmwiki migrate tools-used --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--config PATH` | Optional `sessions_config.json` override (record filters). |

Origin resolution prefers the vault's `llmwiki-state.json` sync keys (`adapter::home-relative-path`), then falls back to a glob under the adapter session store by `sessionId`. Claude Code JSONL is fully supported; Cursor and other non-JSONL stores work when the state key or glob resolves a readable origin path. Missing origins leave `CallMcpTool` entries intact for `wiki_adoption` body fallback.

### `page-kinds` — retype pages off the removed question/comparison kinds

`llmwiki/schema.py` lists five knowledge kinds — `source`, `entity`, `concept`, `project`, `synthesis`. A hand-written page declaring `type: question` or `type: comparison` is a `frontmatter_validity` **error**, and this migration clears it: each such page is retyped to `concept` and moved into `wiki/concepts/` **keeping its filename**, then `wiki/questions/` and `wiki/comparisons/` lose their `_context.md` and are pruned once empty.

Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing.

Two safety rules: a page whose filename is already taken in `wiki/concepts/` is retyped where it stands and reported as a collision rather than overwriting anything, and a removed folder still holding other content is left in place and reported rather than deleted. A vault with no removed-kind page prints `nothing to migrate` and exits 0 without writing.

Implementation: `llmwiki/migrate_page_kinds.py` — in the package rather than under `scripts/`, so it runs from a pip or Homebrew install with no checkout. After migrating, rebuild so `site/` picks up the new locations: `llmwiki build --vault PATH`.
