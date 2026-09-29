---
title: "Obsidian adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, adapters-obsidian, vault-ingestion, project-slug-derivation, wikilink-preservation, redaction-pipeline]
date: 2026-09-28
source_file: 
project: adapters-obsidian
model: 
last_updated: 2026-09-28
---
## Summary

The Obsidian adapter ingests hand-written Markdown notes from Obsidian vaults into [[llmwiki]]'s raw session layer, treating each note as a source document alongside agent-generated transcripts. It preserves YAML frontmatter and native wikilink syntax, derives project slugs from top-level folder names, applies redaction to sensitive data, and currently operates in input-only mode with bidirectional sync planned for v0.2.

## Key Claims

- The adapter reads `.md` files directly (unlike Claude Code and Codex CLI adapters which parse `.jsonl` logs) and passes them to the converter with minimal processing
- Default vault paths are `~/Documents/Obsidian Vault` and `~/Obsidian`, overridable via `adapters.obsidian.vault_paths` in `config.json`
- The adapter skips Obsidian internal folders (`.obsidian/`, `.trash/`, `.git/`, `node_modules/`, `Templates/`) and files smaller than 50 bytes (configurable via `min_content_chars`)
- Project slug is derived from the **top-level folder** under the vault root, lowercased and space-hyphenated (e.g., `03 - Learning` → `03---learning`); notes at vault root get slug `vault-root`
- Output notes land under `raw/sessions/<project-slug>/<flattened-path>.md`, with hierarchical paths below the top-level folder flattened with dashes
- Wikilinks are preserved and work natively, but may not resolve if they point outside the current project slug due to project-based grouping
- Embed links (`![[attachment.png]]`) are treated as images and will 404 unless attachments are copied (not yet implemented in v0.1)
- Obsidian-specific frontmatter (dataview, cssclass) passes through untouched and may not render correctly in the HTML build
- The same redaction pipeline runs on Obsidian notes as session transcripts, redacting API keys, tokens, emails, optional usernames, and custom patterns
- v0.2 roadmap includes bidirectional sync: writing compiled wiki output back to the vault for browsing in Obsidian's graph view and backlinks panel

## Key Quotes

> "Reads plain `.md` files from an Obsidian vault and treats each file as a source document (like a session transcript). This lets you ingest your hand-written notes into the same wiki structure as your agent-generated session markdowns." — the core value proposition

> "Obsidian's `[[wikilink]]` syntax is native to the llmwiki format, so your existing wikilinks will work." — on native link compatibility

> "The **top-level folder** under the vault becomes the project slug." — explains slug derivation logic

> "Attachment handling is not yet implemented." — documents known v0.1 limitation

> "In v0.2 we plan to add **output mode**: write the compiled wiki (`wiki/sources/`, `wiki/entities/`, `wiki/concepts/`) back into your vault" — roadmap direction

## Connections

- [[Adapters]] (entity) — the Obsidian adapter is one of several ingestion adapters alongside Claude Code and Codex CLI
  - fact: Unlike log-parsing adapters, the Obsidian adapter reads pre-written Markdown directly, requiring only lightweight processing (frontmatter preservation, filtering)
  - fact: Currently input-only; bidirectional sync to write wiki output back to the vault is v0.2 roadmap

- [[Obsidian]] (entity) — the note-taking application whose vaults are ingested
  - fact: Default vault paths checked are `~/Documents/Obsidian Vault` and `~/Obsidian`, overridable via configuration
  - fact: Obsidian-specific frontmatter (dataview, cssclass) is passed through untouched
  - fact: v0.2 roadmap includes bidirectional sync to browse compiled wiki in Obsidian's graph view and backlinks panel

- [[llmwiki]] (entity) — the system receiving ingested Obsidian notes
  - fact: Obsidian notes are processed into the `raw/sessions/` layer as source documents, the same as agent-generated markdowns
  - fact: Project slug derivation and folder-tree flattening occur during ingestion

- [[Wikilinks]] (concept) — Obsidian's native `[[target]]` link syntax, compatible with llmwiki's format
  - fact: Existing wikilinks in Obsidian notes are preserved and render as-is in the built site
  - fact: Wikilinks pointing outside the current project slug may fail to resolve (llmwiki groups by project boundary)
  - fact: Aliased wikilinks (`[[target|alias]]`) render with the alias text

- [[Wiki Synthesis]] (concept) — ingestion is part of the larger synthesis pipeline
  - fact: Obsidian notes undergo the same redaction pipeline as other source documents (API keys, tokens, emails, optional usernames, custom patterns)
  - fact: Redaction can be extended with custom patterns (e.g., company identifiers) via `redaction.extra_patterns` in config.json