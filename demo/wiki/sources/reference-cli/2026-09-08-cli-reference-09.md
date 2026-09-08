---
title: "CLI reference (part 9/15: migrate — list or apply a named one-time vault repair)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, vault-migration, cli-migrate, raw-redaction, mcp-tool-metadata, page-kinds, llmwiki-state]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the CLI reference documents `llmwiki migrate`: named, one-time vault repairs after upgrades, outside the daily sync/synth loop. Listing uses `llmwiki migrate` or `--list`; nothing runs until you pass a migration name, with `--dry-run` recommended for previews. New migrations register under the `migrate` subcommand in `llmwiki/cli.py` (not as separate top-level `migrate-X` commands). The text details `state` (legacy dotfiles → unified `llmwiki-state.json`), `raw-redaction` (deterministic `USER` placeholder in `raw/sessions/`), `tools-used` (expand `CallMcpTool` in frontmatter when origin stores still exist), and `page-kinds` (retype removed `question`/`comparison` kinds to `concept` and relocate under `wiki/concepts/`).

## Key Claims

- `llmwiki migrate` has no “run everything” default; each repair is applied only by explicit name (`llmwiki migrate <name>`).
- `migrate raw-redaction` is preferred over `llmwiki sync --force` when fixing username/path redaction in already-synced `raw/`, because old agent transcripts may be gone (~30 days) and force-sync plus re-synth wastes tokens without improving redaction on existing files.
- `migrate tools-used` rewrites `tools_used` / `tool_counts` in `raw/sessions/*.md` only when the originating session file can still be resolved; missing origins are skipped and never get invented MCP names.
- `migrate page-kinds` maps `type: question` and `type: comparison` to `concept`, moves eligible pages into `wiki/concepts/` with the same filename, and intentionally does not rewrite inbound `[[wikilinks]]` because resolution is by filename, not folder.
- `migrate state` is idempotent, merges legacy state files into `llmwiki-state.json`, resolves legacy pending prompts, purges dead `synth_request` queue items, and may enqueue a single `synthesize` task when synth is pending and none is already queued.

## Key Quotes

> "Nothing is applied until you choose a name" — documents opt-in migration design versus implicit bulk upgrades.

> "Prefer this over `llmwiki sync --force` when redaction completeness in existing `raw/` matters" — operational guidance for privacy-safe vaults without re-converting from agent stores.

> "Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder" — explains why `page-kinds` does not require editing referring pages after moves.

## Connections

- [[llmwiki]] (entity) — CLI surface for rare post-upgrade vault repairs (`state`, `raw-redaction`, `tools-used`, `page-kinds`, and related names in examples).
  - fact: Migrations are registered on the `migrate` subcommand in `llmwiki/cli.py`, not as new top-level commands.
- [[Adapters]] (concept) — `tools-used` re-reads session records through the same adapter path as `llmwiki sync` for `CallMcpTool` → `mcp__{server}__{tool}` expansion.
  - fact: Origin lookup prefers `llmwiki-state.json` sync keys, then glob by `sessionId`; Claude Code JSONL is fully supported.
- [[Wiki Synthesis]] (concept) — Most raw-targeting migrations do not touch `wiki/` or enqueue synthesis; `state` may queue one `synthesize` when pending synth work exists and no synthesize task is already pending.
- [[Wikilinks]] (concept) — `page-kinds` relocation relies on filename-based link resolution so inbound links stay valid without edits.
- [[CLAUDE.md]] (concept) — Vault schema and upgrade expectations align with docs that vault migrations are `llmwiki migrate <name>`, listed in upgrade guides rather than ad-hoc scripts only.
