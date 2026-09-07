---
title: "Upgrade guide (part 2/5: 2.0.0 — static site, pipeline, and MCP (from v1.5.0))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, breaking-changes, static-site, adapters, mcp]
date: 2026-09-07
source_file: raw/docs/upgrading/upgrade-guide-02.md
project: upgrading
model: 
last_updated: 2026-09-07
---
## Summary

Version 2.0.0 represents a major architectural shift from dynamic HTTP serving to static site generation, with corresponding changes to the default pipeline automation, adapter system, and MCP tool APIs. The upgrade guide provides detailed breaking changes, required configuration updates via `configure-sources` and `install-automation` wizards, multiple migration paths for legacy data, and optional optimizations for existing vaults.

## Key Claims

- `llmwiki serve` command is removed; users must open generated `<vault>/site/index.html` directly (file:// or via web server)
- The default `llmwiki all` pipeline now includes `sync` and `synth` steps by default; use `--no-sync` or `--no-synth` flags to revert to prior behavior
- Cursor IDE Composer adapter is newly integrated and automatically loaded with `llmwiki sync` after `configure-sources` setup
- MCP tool `wiki_entity_search` is removed and replaced with `wiki_search`; `wiki_lint` now outputs JSON compatible with CLI (`llmwiki lint --json`)
- Multiple migration commands are provided to update legacy data: `migrate page-kinds`, `migrate topic-kinds`, `migrate broken-provenance`, and `migrate tools-used`
- Several CLI commands are removed entirely: `serve`, `consolidate-topics`, `export`, `reindex`, and `synthesize` (replaced by `synth`)
- Static site assets (highlight.js, vis-network) are now vendored in the generated site, enabling offline access

## Key Quotes

> "Stop using `llmwiki serve` — open `<vault>/site/index.html`."
Encapsulates the fundamental shift from dynamic HTTP serving to static file delivery.

> "Cursor IDE Composer ingest works via bare `llmwiki sync` after `configure-sources` Enable"
Highlights new automatic adapter integration that still requires explicit configuration.

> "Prefer `llmwiki synth` — `synthesize` is removed; use `--sources-only` when you want the old sources-only default"
Shows command consolidation and how prior behavior is preserved via explicit flags.

## Connections

- [[llmwiki]] (system) — Core wiki system undergoing v2.0.0 architectural changes
  - fact: Default pipeline changes to `sync` → `synth` → `build` → `graph` → `lint` (was customizable)
  - fact: `install-automation` wizard replaces manual cron job setup with plain-language prompts
  
- [[Static Site]] (output format) — Becomes the primary workflow, replacing HTTP serving
  - fact: Generated `site/index.html` is the user-facing entry point; highlight.js and vis-network are vendored
  - fact: `llmwiki build --local-root PATH` enables portable published paths
  
- [[Adapters]] (ingest system) — Major expansion of automatic adapter support
  - fact: `llmwiki sync` now automatically loads all enabled ingest-ready adapters; `enabled: false` is honored
  - fact: ChatGPT export and Obsidian adapters remain opt-in; Cursor IDE Composer and Cursor Agent CLI are integrated
  
- [[Cursor]] (IDE/Agent tools) — New Cursor IDE Composer adapter integration
  - fact: Cursor IDE global `state.vscdb` is parsed after `configure-sources` setup; alias `--adapter cursor` still resolves
  - fact: `filters.exclude_headless` (default on) skips automated launches for coding-agent adapters
  
- [[Configuration]] (setup system) — Major updates to configuration workflow
  - fact: `configure-sources` wizard is required after upgrade for agent adapter support (#182)
  - fact: `lint.disabled_rules` array in `<vault>/llmwiki.json` allows per-vault lint rule opt-out
  
- [[Knowledge Graph]] (synthesis output) — Now part of default pipeline
  - fact: `graph` command is executed in the default `llmwiki all` pipeline
  
- [[Codex CLI]] (ingest adapter) — Requires reconfiguration
  - fact: `llmwiki configure-sources` must be run after upgrade to classify Codex CLI sessions (#182)

## Contradictions

None identified — this is forward-looking upgrade documentation.