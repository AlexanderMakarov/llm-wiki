---
title: "Phase 1.25 — Research Report (part 1/3)"
slug: phase-1-25-research-report-01
project: phase-1-25-research-report
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/research.md"
content_sha256: 38ce338d0adda637c856de5cd5eeab0485842848f83af1b0e5b0ae87c2afff0b
---

> Part 1 of 3 of **Phase 1.25 — Research Report**.

# Phase 1.25 — Research Report

**Date:** 2026-04-08
**Method:** Cloned every referenced implementation from [Karpathy's gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and the top related GitHub searches into `.temp/` (gitignored) for side-by-side comparison.

This document is the deliverable for **Phase 1.25 Research**, a new phase added to the llmwiki framework (see [docs/framework.md](framework.md)). It is the source of truth for prior-art analysis and the 10x gap that llmwiki targets.

## Summary

15 reference implementations were cloned and analysed. They fall into four clusters:

| Cluster | What they do | Examples | llmwiki differentiation |
|---|---|---|---|
| **Pure-markdown skills** | A Claude Code skill/plugin + CLAUDE.md schema; rely on the agent to do all writes | `kfchou/wiki-skills`, `Astro-Han/karpathy-llm-wiki`, `bashiraziz/llm-wiki-template` | ✅ Same base + native `.jsonl` → markdown + static HTML + multi-agent |
| **Markdown-first + light Python** | Schema + a few Python scripts for ingest/query/lint | `SamurAIGPT/llm-wiki-agent`, `Ss1024sS/LLM-wiki`, `hsuanguo/llm-wiki` | ✅ Same shape + session-transcript adapter + beautiful static site |
| **Obsidian-coupled** | Wiki lives inside an Obsidian vault; user views via Obsidian | `AgriciDaniel/claude-obsidian`, `louiswang524/llm-knowledge-base`, `kytmanov/obsidian-llm-wiki-local`, `remember-md/remember` | 🔀 Obsidian as **one of many** connectors (input adapter) — not the only view |
| **Heavy Python / hosted** | Backend services, databases, hosted demos | `lucasastorian/llmwiki` (Apache, Supabase + MCP, hosted at llmwiki.app), `bitsofchris/openaugi` | ❌ Too heavy — violates llmwiki's stdlib-first rule |
| **Session browsers (not wikis)** | Search/TUI over raw `.jsonl`; no wiki compilation | `raine/claude-history`, `sinzin91/search-sessions` | 🔀 Complementary — they search raw; llmwiki builds the wiki on top |
