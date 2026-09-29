---
title: "Phase 1.25 — Research Report (part 3/3: The 10x gap (feature matrix))"
type: source
tags: [wiki-add, raw-doc, session-transcript, research, feature-matrix, competitive-analysis, obsidian-integration, html-viewer, build-time-redaction]
date: 2026-09-28
source_file: 
project: research
model: 
last_updated: 2026-09-29
---
## Summary

Research report (part 3 of 3) analyzing llmwiki's competitive positioning against 15 reference wiki implementations through a detailed feature matrix, identifying design inspirations from existing projects with explicit attribution, and articulating six v0.1 product decisions that combine borrowed patterns (Karpathy's three-layer structure, slash commands, stale-page detection) with unique differentiators (beautiful HTML viewer, build-time PII redaction, multi-agent adapters, Obsidian I/O).

## Key Claims

- llmwiki's feature matrix includes ~20 capabilities not found in most of the 15 reference implementations, including JSONL session ingestion, Codex CLI adapter, multi-agent adapter pattern, stdlib-only architecture, beautiful static HTML with global search, live-session detection, and build-time redaction of API keys, tokens, emails, and usernames
- The gorgeous static HTML viewer with client-side search (Cmd+K) and syntax highlighting is llmwiki's most visible 10x advantage; none of the 15 reference implementations offer comparable visual output
- Build-time redaction of PII is non-negotiable and uniquely implemented by llmwiki; all reference implementations leak sensitive data by default in transcripts
- Four of 15 reference implementations use Obsidian, indicating it is critical for user adoption; v0.1 ships Obsidian as both input and output adapter (whereas most competitors only support input)
- The stdlib-first approach (no database, MCP, or Node.js) is practiced by ~50% of reference implementations and aligns with llmwiki's core principle of offline-first, zero-cloud operation
- Design patterns (directory layout, slash commands, stale-page detection, local-LLM privacy angle, writer/viewer split, hosted-demo framing) are borrowed with explicit attribution from Karpathy, SamurAIGPT, Ss1024sS, kytmanov, louiswang524, remember-md, and others, but combined into a unique offering

## Key Quotes

> "Ship the HTML viewer as the hero feature. None of the reference implementations have a beautiful static HTML output. This is llmwiki's most visible 10x." — Establishes the gorgeous viewer as the primary competitive differentiator for product positioning.

> "Build-time redaction is non-negotiable — none of the reference implementations do this, and session transcripts leak PII by default." — Identifies security and privacy as core differentiators; no competitor offers this protection.

> "Four of 15 reference implementations use Obsidian — clearly important to users. Make it an optional input adapter, not the only path." — Justifies v0.1 priority on Obsidian support while preserving flexibility for other data sources.

## Connections

- [[llmwiki]] (entity) — the system being positioned through competitive research and feature analysis
  - fact: Feature matrix compares 20+ capabilities across 15 reference implementations to identify differentiation vectors for v0.1

- [[Adapters]] (entity) — plugin architecture enabling multiple integration patterns that are central to llmwiki's differentiation
  - fact: Codex CLI adapter and multi-agent adapter pattern are unique to llmwiki; Obsidian adapter (both input and output) is critical v0.1 feature found in four of 15 reference implementations

- [[Static Site]] (concept) — the beautiful HTML viewer identified as llmwiki's most visible competitive advantage
  - fact: Client-side global search (Cmd+K), syntax highlighting via highlight.js, and gorgeous static output distinguish llmwiki from all 15 reference implementations analyzed

- [[Obsidian]] (entity) — identified as critical for user adoption in v0.1 release
  - fact: Four of 15 reference implementations use Obsidian; research prioritizes shipping Obsidian as both input and output adapter (most competitors only support one direction)

- [[Wiki Synthesis]] (concept) — the broader category of tools researched and positioned against
  - fact: Comparative analysis of 15 wiki synthesis implementations (Karpathy's gist, SamurAIGPT/llm-wiki-agent, Ss1024sS/LLM-wiki, kytmanov/obsidian-llm-wiki-local, louiswang524/llm-knowledge-base, and nine others) informed product roadmap and feature prioritization for v0.1