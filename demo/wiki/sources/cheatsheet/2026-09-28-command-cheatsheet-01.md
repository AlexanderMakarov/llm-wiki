---
title: "Command cheatsheet (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cheatsheet, command-reference, setup-automation, graphify, quality-checks]
date: 2026-09-28
source_file: 
project: cheatsheet
model: 
last_updated: 2026-09-28
---
## Summary

This command cheatsheet documents the llmwiki CLI and slash commands organized by task and lifecycle stage. It covers the 30-second setup workflow, daily automation job configuration via `install-automation`, and 30+ commands grouped into six lifecycle stages. Key sections detail knowledge graph building (with optional Graphify integration for semantic analysis and community detection), quality/lint validation, candidate workflow, and AI synthesis with cost estimation.

## Key Claims

- Slash commands (`/wiki-init`, `/wiki-sync`, `/wiki-graph`, `/wiki-build`) are available in Claude Code and Codex CLI as alternatives to CLI commands
- The `llmwiki install-automation` command configures a daily job with options: `--job ingest` (sync + rebuild only) or `--job maintain` (includes AI synthesis)
- The `llmwiki all` command runs the complete pipeline in order: sync → synth → build → graph → lint (each stage can be optionally skipped)
- Graphify is an optional AI-powered knowledge graph engine installed via `pip install llm-wiki-plus[graph]` that adds Leiden community detection and confidence-scored edges
- The `llmwiki build` command outputs multiple AI-consumable formats: HTML site plus llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, and ai-readme.md
- Cost estimation is available via `llmwiki synth --estimate` before running expensive synthesis operations

## Key Quotes

> "Everything you need on one page. Slash commands work inside Claude Code / Codex CLI; CLI commands run at your terminal." — Defines the dual interface scope of the tool

> "Set the daily job up once and llmwiki keeps itself up to date. The wizard asks what the job should do (collect sessions only, or also summarise them), offers the optional extras, and shows you the exact command line before it writes anything." — Highlights the automation workflow philosophy

> "llmwiki --help lists every subcommand in six lifecycle groups (Start here → Daily loop → Run the loop for me → Look around → Take things out → Rare)" — Documents command organization structure

> "Install Graphify: `pip install llm-wiki-plus[graph]`" — Shows Graphify is an optional addon for advanced graph analysis

## Connections

- [[llmwiki]] (entity) — the core tool this cheatsheet documents
  - fact: Provides 30+ subcommands organized into six lifecycle groups from basic setup through maintenance and introspection
- [[Claude Code]] (entity) — provides slash command interface to wiki operations
  - fact: Slash commands like `/wiki-sync`, `/wiki-graph`, `/wiki-build` work alongside or instead of CLI equivalents
- [[Codex CLI]] (entity) — also supports the documented slash commands
  - fact: Shares the same `/wiki-*` slash command interface as Claude Code
- [[Wiki Synthesis]] (concept) — documented via `llmwiki synth` command and `--job maintain` automation
  - fact: Supports cost pre-estimation with `--estimate` flag; auto-tags pages (up to 5 tags per page with near-dup rejection and stop-word filtering)
- [[Knowledge Graph]] (concept) — built via `llmwiki graph` command with optional Graphify engine
  - fact: Builtin graph uses stdlib (zero dependencies); optional Graphify adds tree-sitter AST extraction, semantic analysis, Leiden community detection, and confidence-scored edges
- [[Lint Rules]] (concept) — quality validation via `llmwiki lint` command
  - fact: Supports selective rule filtering via `--rules` flag and per-vault configuration via `llmwiki.json`
- [[Wikilinks]] (concept) — basis for knowledge graph structure and link validation
  - fact: Lint rules check link integrity and detect orphaned pages; wikilinks form the foundation of the graph visualization
- [[Static Site]] (entity) — output of `llmwiki build` command
  - fact: Compiles wiki markdown into HTML site plus AI-consumable exports (llms.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt)

## Contradictions

None identified. This is reference documentation describing current llmwiki capabilities and command structure.