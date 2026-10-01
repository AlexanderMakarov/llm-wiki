---
title: "llmwiki documentation"
type: source
tags: [wiki-add, raw-doc, session-transcript, index, api-vs-agent-modes, agent-integrations, session-synthesis, offline-first]
date: 2026-10-01
source_file: 
project: index
model: 
last_updated: 2026-10-01
---
## Summary

This documentation hub introduces [[llmwiki]] as a local, stdlib-only Python knowledge base that ingests AI-coding-agent session transcripts and compiles them to an offline static site with no cloud dependency. The system offers two interchangeable operation modes (API for Anthropic API batch processing, Agent for IDE integration), supports 9+ agent adapters, and deploys to GitHub/GitLab Pages, Docker, Vercel, or Netlify. Key features include non-destructive Obsidian/Logseq vault import, MCP server tool integration, prompt caching optimization, and a stable Reader API contract for site output.

## Key Claims

- llmwiki is a local, stdlib-only Python system with zero database, account, or cloud dependency
- Installation and end-to-end setup (first sync) complete in 10 minutes total
- Two interchangeable modes exist: API mode (Anthropic API with parallelism, requires `ANTHROPIC_API_KEY`) and Agent mode (integrated with Claude Code/Codex CLI, no API key)
- Supports 9+ agent adapters: Claude Code, Codex CLI, Cursor Agent CLI, Cursor IDE, Gemini CLI, GitHub Copilot, Obsidian, OpenCode, OpenClaw, and ChatGPT
- Three-layer architecture: `raw/` (transcripts) → `wiki/` (synthesized pages) → `site/` (static HTML)
- Vault import from Obsidian/Logseq is non-destructive by default
- Deployable to multiple platforms including GitHub Pages, GitLab Pages, Docker/GHCR, Vercel, Netlify, and PyPI

## Key Quotes

> "A local, stdlib-only Python knowledge base built from your AI-coding-agent session transcripts. Install in five minutes, then keep every session searchable, interlinked, and offline. No database, no account, no cloud." — Core value proposition and positioning

> "llmwiki runs two interchangeable ways. Pick one, start — you can switch later." — Design philosophy emphasizing low switching cost between modes

> "It's not a vector database, not a RAG framework, not a hosted service. It compiles markdown from JSONL transcripts, writes a static site, and stays out of the way." — Explicit scope boundaries to manage expectations

## Connections

- [[llmwiki]] (entity) — the knowledge base system being documented
- [[Claude Code]] (entity) — primary agent with integrated `/wiki-ingest`, `/wiki-sync`, `/wiki-query` slash commands
- [[Codex CLI]] (entity) — CLI-based agent with live-session filtering support
- [[Adapters]] (concept) — pluggable components enabling 9+ agent integrations
- [[Wiki Synthesis]] (concept) — core process converting transcripts to interlinked markdown pages
- [[Static Site]] (concept) — offline HTML output deployable to multiple platforms
- [[MCP Server]] (entity) — standardized tool server interface with six operations
- [[Knowledge Graph]] (concept) — achieved through wikilink-based session interconnection
- [[Prompt Caching]] (concept) — LLM cost optimization technique documented in reference
- [[GitHub Pages]] (entity) — primary deployment target
- [[Obsidian]] (entity) — supported vault source for non-destructive import
- [[Reader API]] (entity) — stable output contract for compiled site artifacts

## Contradictions

None identified.