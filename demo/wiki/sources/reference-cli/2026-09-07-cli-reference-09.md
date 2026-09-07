---
title: "CLI reference (part 9/15: migrate — list or apply a named one-time vault repair)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, vault-migrations, state-consolidation, username-redaction, frontmatter-schema]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-09.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

Documents the `migrate` CLI subcommand for applying one-time vault repairs after upgrades. Covers five specific migrations: state consolidation (v1.4.0 legacy dotfiles), username redaction in raw sessions, tools-used frontmatter expansion from origin stores, and page-kind retyping (removing question/comparison types). Migrations are opt-in named subcommands with `--dry-run` support, not applied by default.

## Key Claims

- The `migrate` command is for rare, one-time vault repairs after upgrades and is not part of the daily operational loop.
- Migrations must be explicitly named; there is no run-all default.
- The `state` migration consolidates five legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-quarantine.json`, `.llmwiki-pending-prompts/`) into a unified `llmwiki-state.json` and is idempotent.
- The `raw-redaction` migration rewrites usernames in existing `raw/sessions/*.md` files in-place without re-syncing from origin stores or touching `wiki/`.
- The `tools-used` migration expands `CallMcpTool` entries in frontmatter by reading origin store records, but skips sessions where the origin is missing (TTL/deleted).
- The `page-kinds` migration retypes removed `question` and `comparison` kinds to `concept`, preserving filenames so wikilinks remain valid without requiring edits.
- New migrations are registered under `migrate` in `llmwiki/cli.py` as subcommands, not as top-level commands.

## Key Quotes

> "One-time vault repairs after an upgrade — not part of the daily loop. Nothing is applied until you choose a name."

> "Prefer `--dry-run` on a named migration to preview writes."

> "Idempotent: already-redacted files count as `unchanged`."

> "Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing."

## Connections

- [[llmwiki]] (project) — the CLI tool and vault management system being documented
  - fact: Migrations are registered under `migrate` in `llmwiki/cli.py`, not as top-level commands.
  - fact: Implementation scripts live under `scripts/` (e.g., `migrate_state_v1_4_0.py`, `migrate_raw_encoded_username.py`) or in the package itself (e.g., `llmwiki/migrate_page_kinds.py`).

- [[Configuration]] (concept) — state files and configuration are central to migration operations
  - fact: The `state` migration consolidates legacy dotfiles into a unified `llmwiki-state.json`.
  - fact: `tools-used` migration accepts optional `--config PATH` override for record filters.

- [[Frontmatter]] (concept) — migrations modify document frontmatter metadata
  - fact: `tools-used` migration updates `tools_used` and `tool_counts` frontmatter fields by re-reading origin stores.
  - fact: `page-kinds` migration changes the `type:` field and moves pages to `wiki/concepts/` while preserving filenames.

- [[Static Site]] (concept) — the build process is affected by migrations
  - fact: After `raw-redaction` or `tools-used` migrations, rebuild with `llmwiki build --vault PATH` is required for the site to pick up changes.

- [[Wikilinks]] (concept) — page-kinds migration preserves link resolution by filename
  - fact: Pages retyped by `page-kinds` keep their filenames so inbound `[[wikilinks]]` remain valid without referring pages needing edits.

## Contradictions

None identified.