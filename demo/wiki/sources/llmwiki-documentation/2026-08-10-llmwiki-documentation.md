---
title: "llmwiki documentation"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-documentation, offline-knowledge-base, multi-agent-integration, static-site-generation]
date: 2026-08-10
source_file: 
project: llmwiki-documentation
model: 
last_updated: 2026-08-11
---
## Summary

This page is the main documentation hub for [[llmwiki]], establishing its core value proposition as a local, stdlib-only Python knowledge base built from AI coding session transcripts. The documentation presents two operational modes (API and Agent), quick-start tutorials (5-minute installation), integration paths with multiple coding agents, deployment guides, and comprehensive reference material. It explicitly positions llmwiki as a static-site compiler over JSONL transcripts—not a vector database, RAG framework, or hosted service.

## Key Claims

- llmwiki has only one third-party runtime dependency: `markdown` (stdlib-only otherwise)
- Two modes (API and Agent) are interchangeable and can be switched post-install; API mode uses the Anthropic API with per-token costs and batch concurrency, while Agent mode runs serially inside Claude Code or Codex CLI at no additional cost
- Installation and first sync can be completed in 5 minutes, with the promise that failure after 10 minutes is a bug in the docs
- llmwiki integrates with six or more coding agents (Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot, ChatGPT, and others)
- The tool compiles markdown from JSONL transcripts into a static site with offline browsing, cross-linking, and no database or cloud service required

## Key Quotes

> "A local, stdlib-only Python knowledge base built from your AI-coding-agent session transcripts. Install in five minutes, then keep every session searchable, interlinked, and offline. No database, no account, no cloud."

> "What llmwiki is not: It's not a vector database, not a RAG framework, not a hosted service. It compiles markdown from JSONL transcripts, writes a static site, and stays out of the way."

## Connections

- [[llmwiki]] — this page is the primary documentation index for the project
- Multiple coding agents (Claude Code, Codex CLI, Cursor, etc.) — all supported via adapters
- Deployment platforms (GitHub Pages, GitLab Pages, Docker, Vercel, Netlify, Homebrew, PyPI) — documented endpoints for publishing

## Contradictions

- None noted.