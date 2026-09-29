---
title: "Command cheatsheet (part 2/2: Adapters)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cheatsheet, adapters, configuration-management, cli-commands, multi-source-ingestion]
date: 2026-09-28
source_file: 
project: cheatsheet
model: 
last_updated: 2026-09-28
---
## Summary

This is a command reference guide (part 2 of 2) for the [[llmwiki]] CLI, focusing on the [[Adapters]] system that ingest data from diverse sources. It catalogs 2 core adapters (Claude Code, Codex CLI) and 11+ contrib adapters (ChatGPT, Obsidian, Cursor, Gemini CLI, etc.), documents practical CLI flags for sync/build/synth workflows, and explains the three-layer architecture separating immutable transcripts, user-owned pages, and generated static output. Common recipes demonstrate end-to-end workflows from scheduling automation to building with AI synthesis.

## Key Claims

- The adapter system has two tiers: Core adapters (auto-discovered, always loaded) and Contrib adapters (loaded on-demand with `--adapter <name>`).
- [[Obsidian]] integration enables bidirectional workflow: syncing the wiki into an Obsidian vault with `llmwiki sync --vault` and building the site from a vault-based source.
- The three-layer architecture strictly separates `raw/` (immutable transcripts), `wiki/` (user-owned LLM-generated pages), and `site/` (generated static HTML).
- Core adapters are [[Claude Code]] (from `~/.claude/projects/`) and [[Codex CLI]] (from `~/.codex/sessions/`).
- Synthesis can be configured to use [[Ollama]] as a local LLM backend with model and timeout tuning; configuration via `config.json` allows per-adapter lookback dates and custom synthesis backends.

## Key Quotes

> "raw/     IMMUTABLE transcripts (source of truth, never modify)
> wiki/    LLM-generated pages (you own this)  
> site/    GENERATED static HTML (don't edit by hand)"
>
> — Clarifies the clean three-layer separation of concerns and data ownership model.

> "llmwiki adapters                       # list every adapter + who fires on next sync"
>
> — Shows the discovery command for inspecting adapter availability and triggering behavior.

> "llmwiki all" (with note: "Daily, by hand: the same loop as one run, then open site/index.html")
>
> — Demonstrates the typical end-to-end workflow: sync → synth → build → view.

## Connections

- [[llmwiki]] (entity) — the command-line tool this cheatsheet documents
  - fact: Provides CLI for managing 13+ adapter sources and configurable workflows for knowledge base assembly.

- [[Adapters]] (entity) — the core subject of this reference, extracting data from multiple tools and services
  - fact: Includes auto-loaded core adapters (Claude Code, Codex CLI) and 11+ contrib adapters (Obsidian, Cursor, Gemini CLI, ChatGPT, Copilot Chat/CLI, OpenCode, OpenClaw); filtered via `--adapter <name>` and `since` date filtering.

- [[Obsidian]] (entity) — featured as a primary vault integration and adapter source
  - fact: Can sync wiki into an Obsidian vault and build the site from vault-based sources; also serves as an adapter for reading notes directly from vault `.md` files.

- [[Static Site]] (entity) — the generated output format of the build process
  - fact: Produced in `site/` directory (configurable via `build.out_dir`); may include search index and knowledge graph visualization.

- [[Cursor]] (entity) — mentioned as an adapter source with known limitations
  - fact: Has two adapter implementations (`cursor` IDE adapter with limited support per issue #2, and `cursor_cli` for Agent CLI); reads from Cursor workspaceStorage or `~/.cursor/chats/`.

- [[Codex CLI]] (entity) — listed as a core auto-loaded adapter
  - fact: Pulls session transcripts from `~/.codex/sessions/` without requiring explicit selection.

- [[Claude Code]] (entity) — listed as a core auto-loaded adapter
  - fact: Pulls session transcripts from `~/.claude/projects/` without requiring explicit selection.

## Contradictions

None identified.