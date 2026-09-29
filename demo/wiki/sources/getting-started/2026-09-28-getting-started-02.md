---
title: "Getting started (part 2/2: Three commands after install)"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, vault-structure, cli-workflow, install-automation, multi-agent-support]
date: 2026-09-28
source_file: 
project: getting-started
model: 
last_updated: 2026-09-28
---
## Summary

This is Part 2 of the Getting Started guide for [[llmwiki]] (entity), covering the three core commands (sync, synth, build), the vault directory structure where user data is isolated from the git clone, non-session document ingestion via `llmwiki add`, automated daily jobs via `install-automation`, and recent features including model pages and multi-agent agent support from Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI.

## Key Claims

- The three core commands are `llmwiki sync` (pull sessions from agent store), `llmwiki synth` (fill wiki sources and harvest candidates), and `llmwiki build` (compile to static HTML)
- `llmwiki all` runs all three commands sequentially, then builds the knowledge graph and reports quality metrics
- `llmwiki add` ingests multiple document types: local markdown, web pages, PDFs, and folders into `<vault>/raw/docs/`
- Synthesis is optional when adding documents; `--synthesize` flag or later `llmwiki synth` run enables LLM processing
- Vault data lives outside the git clone and is never committed; the clone stays clean with only code and demo seeds
- `llmwiki install-automation` sets up a daily job with a wizard prompting whether to collect sessions only or also synthesize them
- Recent versions support model pages, auto-detected project topics, and simultaneous sync from multiple agents with colored badges per agent
- [[Wiki Synthesis]] (concept) is Karpathy layer 2, requiring an LLM in the loop (e.g., Claude Code with `/wiki-ingest` command) to read raw sessions and write wiki pages

## Key Quotes

> "Everything lands in your **vault** directory (the `vault.default_path` from step 2), *not* the git clone"

This establishes the foundational architectural principle: user data is completely isolated from the repository, never committed, and never sent anywhere.

> "You only have to do that by hand once. Hand the loop to a daily job"

Captures the progression from manual workflow to sustainable automation, which is central to operational use.

> "The agent reads the source markdowns from the vault, writes summary pages, cross-links entities, and updates `wiki/index.md`"

Describes the core [[Wiki Synthesis]] (concept) workflow that transforms raw sessions into structured wiki pages.

## Connections

- [[llmwiki]] (entity) — the entire system being documented
  - fact: Provides three sequential commands (sync, synth, build) plus `llmwiki all` to run all three and report metrics.
  - fact: Vault root directory segregates raw sessions, wiki pages, and generated site from the git clone.

- [[Wiki Synthesis]] (concept) — the LLM-powered wiki generation layer (Karpathy layer 2)
  - fact: Synth step populates `wiki/sources/`, `wiki/entities/`, `wiki/concepts/` with cross-linked pages.
  - fact: Synthesis is optional in `llmwiki add` and can be deferred or run separately via `llmwiki synth`.

- [[Adapters]] (entity) — document ingestion system  
  - fact: `llmwiki add` supports markdown files, web pages, PDFs, and folders as first-class input alongside sessions.
  - fact: Raw documents land in `<vault>/raw/docs/` and trigger site rebuild unless `--no-build` is passed.

- [[Static Site]] (entity) — the generated website output
  - fact: `llmwiki build` compiles raw and wiki content to plain HTML files in `<vault>/site/`.
  - fact: Site includes interactive navigation (⌘K/Ctrl+K for command palette, `/` for search, `j`/`k` for table navigation, `?` for help).

- [[MCP Server]] (entity) — agent integration and vault access
  - fact: Agents point to `python3 -m llmwiki.mcp` to access `wiki_search` and `wiki_read_page` tools against the same vault.
  - fact: Multi-agent support allows simultaneous sync from Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI with colored badges per agent.

- [[Claude Code]] (entity) — primary agent for wiki synthesis
  - fact: Runs `/wiki-ingest <path>` command inside a Claude Code session to read raw markdowns and generate wiki pages with entity cross-links.

## Contradictions

None identified.