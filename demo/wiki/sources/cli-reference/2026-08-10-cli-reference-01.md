---
title: "CLI reference (part 1/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, vault-integration, session-ingestion, argparse-guardrail, state-persistence]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

Comprehensive reference documentation for the `llmwiki` CLI package was created, covering all four main subcommands (`init`, `sync`, `add`, `remove`) with flags, examples, and expected outputs. The documentation is machine-validated against the live argparse tree to ensure every command and flag that ships is documented.

## Key Claims

- Every CLI subcommand and flag must be documented here or it won't ship; failure to document is caught by a guardrail test
- The `init` command is idempotent and creates three core directories (raw/, wiki/, site/) plus nine seeded navigation files
- The `sync` command walks adapters, converts .jsonl sessions to markdown, reconciles wiki/index.md, and auto-builds/lints by default
- The `add` command ingests external documents (URLs, files, folders) into raw/docs/ with optional title, project, and tag overrides
- The `remove` command cascade-deletes raw docs and all derived artifacts (state keys, wiki pages) to prevent orphans and dangling backlinks
- Vault-overlay mode allows syncing directly into Obsidian or Logseq vaults instead of the repository's own directories
- There is intentionally no `sync --dry-run` flag; `sync --status` is the observability alternative
- Application state is persisted in a single `llmwiki-state.json` file, configured once at CLI entry

## Key Quotes

> "If a command isn't listed here it isn't shipping." — Establishes documentation-as-API contract: the reference is the source of truth for what ships.

> "This page is generated against the live argparse tree, so adding a flag without documenting it will fail the guardrail test." — Validation mechanism ensuring CLI and documentation stay in sync.

> "Idempotent. Safe to re-run — it never overwrites files that exist." — Design principle for `init`, enabling safe re-initialization.

> "State lives in `llmwiki-state.json` (configured once at CLI entry via `--vault` / `vault.default_path`)." — Architectural detail on state persistence and vault selection.

## Connections

- [[LLM Wiki]] — the main project whose CLI is comprehensively documented here
- [[Obsidian]] — supported integration target via vault-overlay mode
- [[Logseq]] — supported integration target via vault-overlay mode

## Contradictions

- None identified.