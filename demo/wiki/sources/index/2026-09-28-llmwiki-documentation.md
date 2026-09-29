---
title: "llmwiki documentation"
type: source
tags: [wiki-add, raw-doc, session-transcript, index, mcp-server, prompt-caching, batch-api, agent-adapters, offline-first]
date: 2026-09-28
source_file: 
project: index
model: 
last_updated: 2026-09-28
---
## Summary

This documentation hub establishes [[llmwiki]] (entity) as a local, stdlib-only Python knowledge base that compiles AI-coding-agent session transcripts into a searchable, interlinked, offline static site with no external infrastructure. It describes two operational modes—API mode (per-token Anthropic API cost) and Agent mode (integrated into Claude Code/Codex CLI with no separate charge)—and documents support for ten agent adapters. The docs detail deployment targets (GitHub Pages, GitLab Pages, Docker, Vercel/Netlify, PyPI, Homebrew), an MCP server interface, and internal architecture, while claiming 5-minute setup and only `markdown` as a runtime dependency.

## Key Claims

- llmwiki has only `markdown` as a third-party runtime dependency; all other code uses the Python standard library
- API mode and Agent mode are described as "interchangeable"—users can switch between them without rebuilding
- Installation takes 5 minutes; first sync (from install to browsable site) also takes 5 minutes
- Ten agent adapters are documented: Claude Code, Codex CLI, Cursor Agent CLI, Cursor IDE, Gemini CLI, Copilot, Obsidian, OpenCode, OpenClaw, ChatGPT
- The MCP server exposes exactly six stable tools: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`
- System architecture uses three layers: raw/ (ingest JSONL), wiki/ (synthesis to markdown), site/ (static output)
- Prompt caching and batch API are supported in API mode to reduce token costs

## Key Quotes

> "A local, stdlib-only Python knowledge base built from your AI-coding-agent session transcripts. Install in five minutes, then keep every session searchable, interlinked, and offline. No database, no account, no cloud."
>
> Core value proposition: offline storage, rapid onboarding, minimal vendor lock-in, zero infrastructure.

> "It compiles markdown from JSONL transcripts, writes a static site, and stays out of the way. The only third-party runtime dependency is `markdown`."
>
> Defines boundaries: not a vector database, RAG framework, or hosted service—a pure ingestion→compile→deploy pipeline.

## Connections

- [[llmwiki]] (entity) — the system described; ingests session transcripts from agents and synthesizes them into an offline wiki
- [[Claude Code]] (entity) — supported via Agent mode with slash commands (`/wiki-ingest`, `/wiki-sync`, `/wiki-query`)
  - fact: Agent mode requires no separate Anthropic API key when using Claude Code
- [[Codex CLI]] (entity) — supported with live-session filtering from `~/.codex/sessions/`
- [[Cursor]] (entity) — two adapters: Cursor Agent CLI and Cursor IDE
- [[Gemini CLI]] (entity) — included in the ten-adapter ecosystem
- [[GitHub Copilot]] (entity) — supported adapter
- [[Obsidian]] (entity) — can import existing vaults non-destructively via `llmwiki sync --vault <path>`
- [[Adapters]] (entity) — nine additional agent integrations beyond the primary two (Claude Code, Codex CLI); new adapters can be authored following a documented protocol
  - fact: Adapters are the pluggable system connecting any AI agent to the ingestion pipeline
- [[MCP Server]] (entity) — provides stdio interface allowing Claude and other MCP-capable clients to query and modify the wiki
  - fact: Exposes `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add` as stable tools
- [[GitHub Pages]] (entity) — primary documented deployment target; also supports GitLab Pages, Docker, Vercel/Netlify
- [[Prompt Caching]] (concept) — supported in API mode alongside batch processing to reduce inference costs
- [[Static Site]] (entity) — the compiled output format of the three-layer architecture
- [[Knowledge Graph]] (concept) — enables cross-page navigation within the compiled site via wikilinks
- [[Wiki Synthesis]] (concept) — the core process of ingesting raw JSONL transcripts and compiling them into structured wiki markdown
  - fact: API mode supports batch + parallel synthesis; Agent mode is serial but cost-free

## Contradictions

None identified.