---
title: "Command cheatsheet (part 2/2: Adapters)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cheatsheet, adapters, cli-reference, configuration, obsidian-integration, workflow-recipes]
date: 2026-09-07
source_file: 
project: cheatsheet
model: 
last_updated: 2026-09-07
---
## Summary

This cheatsheet documents the practical operation of [[llmwiki]], covering the adapter ecosystem (core and contrib), Obsidian bidirectional sync, commonly-used CLI flags, configuration file structure, and the immutable three-layer architecture (raw/, wiki/, site/). It serves as a reference for both new and experienced users of the tool.

## Key Claims

- [[llmwiki]] has two core adapters (`claude_code`, `codex_cli`) that are auto-discovered and always loaded, plus nine contrib adapters (`chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`, `cursor_cli`, `gemini_cli`, `obsidian`, `opencode`, `openclaw`) that load on-demand via `--adapter <name>`
- The tool enforces a three-layer architecture: `raw/` holds immutable source transcripts; `wiki/` contains LLM-generated pages organized by type (sources, entities, concepts, projects, syntheses); `site/` contains the generated static HTML output
- [[Obsidian]] integration is bidirectional: the `obsidian` adapter ingests `.md` files from a vault, and the `--vault` flag exports the built wiki into an external Obsidian vault with configurable layout (entities, concepts, sources, syntheses subdirectories)
- Configuration is centralized in `config.json` with per-adapter lookback filters (`adapters.<name>.since`) that override the shared `filters.since` setting, allowing fine-grained control over sync lookback windows
- Exit code `2` signals a usage/argument error; `0` indicates success; `1` indicates operational failure

## Key Quotes

> "raw/     IMMUTABLE transcripts (source of truth, never modify)" — establishes the immutability contract and single source of truth at the foundational layer

> "llmwiki sync --vault ~/Documents/Obsidian\ Vault/my-wiki" — demonstrates the bidirectional sync pattern for exporting the wiki into an external Obsidian vault

> "--force-resync | Override the newer-schema/corrupt-state guard (#29); implies `--force`, may duplicate `raw/`" — hints at schema migration safety and state file management considerations

## Connections

- [[llmwiki]] (system) — the command-line tool documented in this cheatsheet
  - fact: Supports 11 total adapters (2 core + 9 contrib) for ingesting multi-source session data
  - fact: Uses a shared state file (`llmwiki-state.json`) that unifies queue, sync, synth, and quarantine state across runs
- [[Adapters]] (concept) — the pluggable architecture for data ingestion from different AI tools and platforms
  - fact: Each adapter has its own source directory and optional per-adapter `since` filter for selective syncing
  - fact: Support map and headless rules documented in `multi-agent-setup.md` (referenced but not shown here)
- [[Obsidian]] (tool) — bidirectionally integrated with [[llmwiki]] for vault storage and knowledge management
  - fact: Can be used both as a data source (via `--adapter obsidian`) and as an export target (via `--vault` flag)
  - fact: Vault subfolder layout is configurable via `vault.layout.*` keys in config.json
- [[Configuration Reference]] (reference) — the doc implies this exists as a deeper reference for all config options
  - fact: `config.json` is organized into logical sections: vault, graph, build, schedule, synthesis, filters, adapters, truncation
  - fact: Schema and defaults shown here; full descriptions and rationale in the referenced configuration reference
- [[Codex CLI]] (tool) — listed as one of two core adapters sourcing from `~/.codex/sessions/`
- [[Claude Code]] (tool) — listed as one of two core adapters sourcing from `~/.claude/projects/`
