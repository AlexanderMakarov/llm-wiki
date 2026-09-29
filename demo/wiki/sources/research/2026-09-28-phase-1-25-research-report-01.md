---
title: "Phase 1.25 — Research Report (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, research, prior-art-analysis, markdown-wiki, karpathy-gist, obsidian-adapter, static-generation]
date: 2026-09-28
source_file: 
project: research
model: 
last_updated: 2026-09-29
---
## Summary

Phase 1.25 research analyzed 15 LLM wiki implementations cloned from Karpathy's gist and related GitHub searches, categorizing them into five architectural clusters: pure-markdown skills, markdown+Python hybrids, Obsidian-coupled systems, heavy Python backends, and session browsers. The analysis maps llmwiki's differentiation strategy: treating Obsidian as one of many optional input adapters (not the required interface), generating beautiful static sites, maintaining stdlib-first simplicity, and compiling structured wikis above raw session search.

## Key Claims

- Fifteen reference implementations were analyzed and grouped by architecture and design philosophy
- Obsidian-coupled wikis lock the user interface to Obsidian; llmwiki treats Obsidian as one of many optional vault connectors via the [[Adapters]] pattern
- llmwiki rejects heavy Python backends and hosted services to maintain stdlib-first design (e.g., rejecting Apache-backed implementations with Supabase + MCP)
- Static HTML generation is a key llmwiki differentiator, present in markdown+Python hybrids and llmwiki but missing from pure-markdown skill implementations
- Session browsers and llmwiki serve complementary roles: browsers search raw `.jsonl` transcripts; llmwiki builds structured wiki structure above that layer

## Key Quotes

> "Obsidian as **one of many** connectors (input adapter) — not the only view" — the core architectural principle distinguishing llmwiki from Obsidian-centric systems

> "Too heavy — violates llmwiki's stdlib-first rule" — the design constraint rejecting hosted and backend-heavy implementations

## Connections

- [[llmwiki]] (entity) — the subject of competitive analysis across five implementation clusters
  - fact: llmwiki combines markdown foundations, session-transcript ingestion, static site generation, and multi-adapter architecture
- [[Obsidian]] (entity) — positioned as one of many optional input adapters, not the required user view
  - fact: Obsidian-coupled cluster treats Obsidian as the primary interface; llmwiki makes it optional via adapters
- [[Static Site]] (concept) — a key differentiator; llmwiki generates beautiful static HTML for publishing
  - fact: Pure-markdown skill implementations and session browsers skip static site generation; llmwiki adds a publishing layer
- [[Adapters]] (entity) — the architectural pattern enabling Obsidian, Logseq, and other vault sources as interchange points
  - fact: Multiple adapters make Obsidian optional rather than mandatory
- [[Wiki Synthesis]] (concept) — the compilation process that distinguishes llmwiki from session search tools
  - fact: Session browsers search raw transcripts; llmwiki builds structured wiki structure and relationships above that

## Contradictions

None identified. This is primary competitive research establishing prior-art taxonomy and positioning.