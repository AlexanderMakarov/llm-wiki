---
title: "CLI reference (part 10/19: migrate — list or apply a named one-time vault repair)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, migrate, vault-repair, raw-redaction, state-migration]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation describes the `migrate` command for applying one-time vault repairs after [[llmwiki]] upgrades. It covers five major migration operations—legacy state consolidation, username redaction/unredaction, and tool-used expansion—all designed with safety-by-default semantics requiring explicit invocation and supporting dry-run previews.

## Key Claims

- The `migrate` command handles one-time vault repairs after [[llmwiki]] upgrades and is not part of daily operations; no migration runs without explicit invocation by name.
- There is no run-everything default; each migration must be explicitly named and typically benefits from a `--dry-run` preview before execution.
- `raw-redaction` deterministically rewrites usernames in raw/sessions/*.md files to use a USER placeholder and is preferred over `llmwiki sync --force` when session stores have expired (typically 30-day TTL).
- `raw-unredaction` reverses redaction by substituting real usernames for the USER placeholder, but cannot distinguish between redacted paths and intentionally-typed placeholder text in documentation.
- The legacy state migration (v1.4.0) consolidates multiple dotfiles (.llmwiki-state.json, .llmwiki-synth-state.json, .llmwiki-queue.json, etc.) into a unified llmwiki-state.json; the operation is idempotent.
- Migrations are registered in llmwiki/cli.py as named subcommands under `migrate` rather than as separate top-level commands.

## Key Quotes

> "One-time vault repairs after an upgrade — not part of the daily loop."
  — Clarifies that migrations are post-upgrade maintenance, not routine operations.

> "There is no run-everything default. Prefer `--dry-run` on a named migration to preview writes."
  — Establishes the safety-first design principle of explicit invocation and optional preview.

> "Prefer this over `llmwiki sync --force` when redaction completeness in existing `raw/` matters: agent transcripts are usually retained only ~30 days, so older sessions often have no source left to re-convert."
  — Explains when to use the redaction-specific migration rather than full re-sync, due to session TTL constraints.

> "It cannot tell a redacted path from a placeholder path a person typed on purpose. Prose that quotes a rule such as 'use `/home/USER/…`' is rewritten to your real home path too."
  — Documents the key limitation of unredaction when applied to documentation containing placeholder examples.

## Connections

- [[llmwiki]] (entity) — The CLI tool whose migrate command and subcommands are documented.
  - fact: Migrations are registered in llmwiki/cli.py as named subcommands rather than as separate top-level commands.

## Contradictions

None identified.