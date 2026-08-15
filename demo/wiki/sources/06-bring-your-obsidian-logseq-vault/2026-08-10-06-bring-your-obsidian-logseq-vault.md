---
title: "06 · Bring your Obsidian / Logseq vault"
type: source
tags: [wiki-add, raw-doc, session-transcript, 06-bring-your-obsidian-logseq-vault, vault-overlay, non-destructive-writes]
date: 2026-08-10
source_file: 
project: 06-bring-your-obsidian-logseq-vault
model: 
last_updated: 2026-08-11
---
## Summary

This tutorial introduces vault-overlay mode in [[llmwiki]], which allows the CLI to write wiki pages (entities, concepts, sources, syntheses) directly into existing [[Obsidian]] or [[Logseq]] vaults without requiring migration. The feature auto-detects vault format, routes new pages to sensible defaults per vault type, and uses idempotent syncing to safely append new connections to user-owned notes without overwriting them.

## Key Claims

- llmwiki can target existing [[Obsidian]] or [[Logseq]] vaults with the `--vault` flag instead of maintaining a separate `raw/` + `wiki/` tree.
- Vault format is auto-detected from directory markers: `.obsidian/` signals Obsidian, `logseq/` or root `config.edn` signals Logseq; if both exist, Logseq takes precedence.
- Obsidian pages land in `Wiki/<type>/` directories with bare wikilinks (`[[RAG]]`); Logseq pages land in `pages/` with namespace-aware links (`[[wiki/entities/RAG]]`).
- Sync is non-destructive by default: existing pages are skipped on writes, and only new inbound wikilinks are appended idempotently under `## Connections`.
- The round-trip workflow is safe: users can manually enhance pages after initial sync, and re-running sync will append only new discovered links without duplicating previous additions.

## Key Quotes

> "vault-overlay mode compiles your vault **in place** — your existing notes stay untouched, new pages land where you tell them." — Rationale for supporting in-place integration.

> "The second run **never overwrites** an existing page... **idempotently** (re-running doesn't duplicate). Your prose stays intact." — Core guarantee that user edits are preserved across sync runs.

> "If it can add new inbound wikilinks under `## Connections`, it does so **idempotently**" — Technical mechanism for safe incremental ingestion.

## Connections

- [[llmwiki]] — CLI tool implementing vault-overlay mode; provides `--vault`, `--dry-run`, `--allow-overwrite` flags and Python API for vault operations.
- [[Obsidian]] — primary vault platform supported; uses `.obsidian/` marker and `Wiki/<type>/` default layout.
- [[Logseq]] — secondary vault platform supported; uses `logseq/` or `config.edn` marker and `pages/wiki___type___slug.md` naming.