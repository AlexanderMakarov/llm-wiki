---
title: "Command cheatsheet (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cheatsheet, cli-reference, automation, knowledge-graph, static-site, daily-workflow, setup-guide, ai-exports]
date: 2026-09-07
source_file: 
project: cheatsheet
model: 
last_updated: 2026-09-07
---
## Summary

Comprehensive command reference for [[llmwiki]] documenting the 30-second bootstrap sequence, daily automation setup via `install-automation` wizard, and the complete CLI command lifecycle. Covers synthesis cost transparency, static site generation, knowledge graph engines (builtin and Graphify), quality assurance via 17-rule linting, and candidate workflow management.

## Key Claims

- The core bootstrap path is `/wiki-init` → `/wiki-sync` → `/wiki-graph` → `/wiki-build` → open `site/index.html` → `llmwiki install-automation`.
- `llmwiki all` executes the complete pipeline (sync → synth → build → graph → lint) in one command with opt-out flags per stage.
- `install-automation` offers two modes: `--job ingest` (no LLM calls, no cost) and `--job maintain` (includes AI synthesis).
- `llmwiki synth --estimate` reports cost *before* synthesis; re-running `install-automation` replaces an existing job instead of duplicating it.
- The static site output is plain files with no runtime dependencies; `llmwiki build` generates multiple AI-consumable exports (llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt).
- Graphify is an optional AI-powered graph engine requiring `pip install llm-wiki-plus[graph]` that provides semantic analysis and community detection; builtin wikilink graph is zero-dependency fallback.
- 17 wiki-quality rules are enforced by `llmwiki lint` with per-rule filtering, CI flags, and vault-level rule override support.

## Key Quotes

> "Everything you need on one page. Slash commands work inside Claude Code / Codex CLI; CLI commands run at your terminal." — Establishes the dual-interface model

> "`--job maintain` sends session text to your AI provider — run `llmwiki synth --estimate` first to see what a run costs." — Emphasizes cost transparency and user control before synthesis

> "Set the daily job up once and llmwiki keeps itself up to date. The wizard asks what the job should do…and shows you the exact command line before it writes anything." — Describes the `install-automation` wizard UX

## Connections

- [[llmwiki]] (system) — the primary system; all commands are llmwiki subcommands or related slash commands.
- [[Codex CLI]] (interface) — provides slash command support for `/wiki-sync`, `/wiki-graph`, `/wiki-build`, `/wiki-ingest`, `/wiki-update`, `/wiki-query`, `/wiki-lint`, `/wiki-reflect`.
- [[Claude Code]] (interface) — alternative environment for slash command execution alongside [[Codex CLI]].
- [[Static Site]] (output) — the compiled HTML wiki is plain files in `site/` with no runtime server.
  - fact: `llmwiki build` generates HTML, AI exports (llms.txt, graph.jsonld), and metadata (sitemap.xml, robots.txt, rss.xml).
- [[Knowledge Graph]] (feature) — graph generation via `llmwiki graph` with two engines.
  - fact: Builtin wikilink graph uses stdlib; Graphify (optional) adds semantic analysis and Leiden community detection.
- [[GitHub Actions]] (automation) — implied deployment target for daily job scheduling.
- [[Configuration Reference]] (documentation) — referenced for full `install-automation` flag table.

## Contradictions

None identified.