---
title: "Configuration (part 3/3: CLI flags)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, cli-flags, sync-command]
date: 2026-09-28
source_file: 
project: configuration
model: 
last_updated: 2026-09-28
---
## Summary

This document specifies the CLI reference for llmwiki, detailing flags for the sync, build, init, and adapters commands. It covers configuration options for supported adapters (Claude Code, Obsidian, Codex CLI), including vault paths, exclusions, and thresholds. Additional sections document .llmwikiignore patterns, theme customization, and MCP tool timeout configuration.

## Key Claims

- By default, per-file conversion errors during `llmwiki sync` do not fail the entire run; pass `--fail-on-errors` to change this for CI/scripted pipelines
- There is no `sync --dry-run` flag; use `add --dry-run` for intake previews or `sync --status` to inspect state
- Obsidian adapter defaults to checking `~/Documents/Obsidian Vault` and `~/Obsidian` and can be configured via `config.json`
- Codex CLI is the designated production core adapter
- MCP tools default to 120-second wall-clock timeouts, configurable per tool in `config.json`
- `.llmwikiignore` uses gitignore-style patterns to skip sessions during sync
- Durable lookback dates are configured via `filters.since` in `config.json` or per-adapter via `adapters.<name>.since`

## Key Quotes

> "Per-file conversion errors do not fail the run by default: each one is counted in the summary, recorded in `llmwiki-state.json` quarantine entries, and visible via `llmwiki sync --status`, while the rest of the corpus still converts. Pass `--fail-on-errors` for a hard gate (CI, scripted pipelines that must not proceed past a partial sync)."

This documents the intentional graceful-degradation design, allowing partial syncs by default with hard-fail mode for CI environments.

> "**Codex CLI**: **Production** core adapter. Default roots: `~/.codex/sessions` and `~/.codex/projects`."

Establishes Codex CLI as the primary production adapter distinct from experimental or opt-in adapters.

## Connections

- [[llmwiki]] (entity) — the entire tool whose CLI flags and configuration are documented here
  - fact: `llmwiki sync` supports `--adapter` to run only named adapters, `--vault` to write to external vaults, and `--status` to inspect state without syncing
  - fact: `llmwiki build` supports `--synthesize` to generate an Overview and `--out` to specify output directory

- [[Adapters]] (entity) — configuration details for three named adapters
  - fact: Adapter configuration is provided via `adapters.<name>` blocks in `config.json`
  - fact: Codex CLI is the designated production core adapter with `~/.codex/sessions` and `~/.codex/projects` as default roots

- [[Claude Code]] (entity) — adapter with session store at `~/.claude/projects/` by default, overridable in config
  - fact: Default location can be overridden via the adapter config block

- [[Obsidian]] (entity) — note-taking adapter with configurable vault paths and content filters
  - fact: Defaults check `~/Documents/Obsidian Vault` and `~/Obsidian` in order
  - fact: Configuration options include `vault_paths`, `exclude_folders`, and `min_content_chars`

- [[Codex CLI]] (entity) — production core adapter with roots at `~/.codex/sessions` and `~/.codex/projects`
  - fact: Roots can be overridden with `adapters.codex_cli.roots` in config

- [[MCP Server]] (entity) — MCP tool timeouts configured centrally in `config.json`
  - fact: Default timeout is 120 seconds for long-running tools like `wiki_add` and `wiki_sync`
  - fact: Per-tool overrides live under `mcp.tool_timeouts` in config

## Contradictions

None identified.