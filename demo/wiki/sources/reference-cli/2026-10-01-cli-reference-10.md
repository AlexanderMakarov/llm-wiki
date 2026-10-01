---
title: "CLI reference (part 10/19: migrate — list or apply a named one-time vault repair)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, migrate-command, vault-repair, username-redaction, state-migration]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Documents the `migrate` subcommand for one-time vault repairs in [[llmwiki]], covering state consolidation (v1.4.0), username redaction/unredaction in session files, and MCP tool metadata expansion. No automatic run-all capability; all migrations support `--dry-run` for safe preview.

## Key Claims

- The migrate command handles rare, one-time vault repairs after upgrades, not daily operations, with explicit opt-in for each named migration rather than a run-everything default
- New migrations register under migrate in llmwiki/cli.py, not as top-level commands; older references to `migrate-X` should be read as `migrate <name>`
- The raw-redaction and raw-unredaction migrations only modify raw/sessions/ files, leaving wiki/ content and synthesis state untouched
- The raw-unredaction migration cannot distinguish between accidentally redacted paths and intentionally-typed placeholder text, risking unwanted substitution in quoted documentation
- The tools-used migration only succeeds if the original agent session file exists; missing origins are skipped unchanged rather than invented

## Key Quotes

> "Rare. One-time vault repairs after an upgrade — not part of the daily loop. List available migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing is applied until you choose a name."

Establishes the safety-first design: no run-everything default, explicit opt-in required.

> "In a vault synced from several machines or accounts, that name is wrong for files that came from the others."

Documents a key limitation of raw-unredaction in multi-machine environments.

> "Prefer `--dry-run` on a named migration to preview writes."

Recommended best practice for all migrations.

## Connections

- [[llmwiki]] (entity) — the CLI tool system providing the migrate subcommand for vault repairs
  - fact: New migrations register under migrate in llmwiki/cli.py, not as top-level commands
- [[Frontmatter]] (concept) — the tools-used migration updates metadata fields in session files
  - fact: The tools-used migration rewrites tools_used and tool_counts in raw/sessions/ frontmatter when origin session files exist