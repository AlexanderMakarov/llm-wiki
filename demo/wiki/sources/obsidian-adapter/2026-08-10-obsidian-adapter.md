---
title: "Obsidian adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, obsidian-adapter, vault-ingestion, markdown-to-wiki, wikilinks]
date: 2026-08-10
source_file: 
project: obsidian-adapter
model: 
last_updated: 2026-08-11
---
## Summary

The Obsidian adapter is an input-only [[llm-wiki]] adapter (v0.1) that reads `.md` files from Obsidian vaults and ingests them into the wiki's `raw/` layer as source documents, preserving frontmatter and wikilinks while filtering Obsidian internals and stub files. A v0.2 roadmap entry traces plans for bidirectional sync (output mode) to write compiled wiki content back into Obsidian vaults.

## Key Claims

- The adapter differs from Claude Code and Codex CLI adapters by accepting pre-written markdown directly rather than parsing structured logs into markdown
- Project slugs are derived from the top-level folder under the vault root (e.g., `~/Documents/Obsidian Vault/03 - Learning/` becomes `03---learning`)
- Notes at vault root with no parent folder receive the slug `vault-root`
- YAML frontmatter in Obsidian notes is preserved verbatim; Obsidian-specific fields (dataview, cssclass) are passed through unchanged
- Obsidian wikilinks work natively but may not resolve if they target notes outside the current project slug
- The same privacy redaction pipeline (usernames, API keys, tokens, emails) that applies to Claude sessions also runs on Obsidian notes
- Default vault paths are checked in order (`~/Documents/Obsidian Vault`, then `~/Obsidian`); custom paths and exclude patterns are configurable
- Attachment handling is not yet implemented (v0.2 roadmap item)

## Key Quotes

> "Unlike the Claude Code and Codex CLI adapters — which parse `.jsonl` into markdown — the Obsidian adapter reads markdown that you've already written, and hands it straight to the converter for lightweight processing"

— clarifies the architectural difference from existing adapters

> "Currently the Obsidian adapter is **input-only**: it reads your vault into llmwiki's `raw/` layer. In v0.2 we plan to add **output mode**: write the compiled wiki back into your vault"

— delineates the current scope and future direction

## Connections

- [[llm-wiki]] — this adapter integrates Obsidian vaults into the wiki ingestion pipeline
- [[Redaction Pipeline]] — the adapter applies the same privacy filtering to hand-written notes as to session transcripts

## Contradictions

None identified with documented wiki content (no prior records of Obsidian adapter design decisions in context).