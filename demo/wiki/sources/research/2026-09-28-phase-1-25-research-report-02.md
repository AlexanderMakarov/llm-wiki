---
title: "Phase 1.25 — Research Report (part 2/3: Per-repo analysis)"
type: source
tags: [wiki-add, raw-doc, session-transcript, research, wiki-competitive-analysis, prior-art-analysis, distribution-models, design-patterns, adapter-architecture]
date: 2026-09-28
source_file: 
project: research
model: 
last_updated: 2026-09-29
---
## Summary

This research report surveys 17+ open-source LLM wiki implementations, categorizing them by architecture (pure markdown, markdown+light Python, Obsidian-coupled, full-stack hosted) and identifying feature gaps. The analysis establishes [[SamurAIGPT/llm-wiki-agent]] as the closest prior art, confirms [[Obsidian]] as a compelling optional viewer rather than a requirement, and validates [[llmwiki]]'s core positioning: lightweight, local-first, zero-infrastructure design as a practical alternative to heavier hosted solutions.

## Key Claims

- Pure-markdown skills-based wikis (wiki-skills, karpathy-llm-wiki) achieve minimal cognitive footprint but lack session-transcript ingestion and static HTML compilation.
- SamurAIGPT/llm-wiki-agent is the closest prior art, featuring documented schema, slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph`), and a vis.js knowledge graph builder—llmwiki inherits its directory layout and command naming.
- Obsidian-coupled implementations (AgriciDaniel/claude-obsidian) lock users into a single viewer; [[llmwiki]] should offer [[Obsidian]] as an optional [[Adapters|adapter]], not a prerequisite.
- Full-stack hosted approaches (lucasastorian/llmwiki, bitsofchris/openaugi) require external infrastructure (Supabase, S3, Node, [[MCP Server]]) that violates llmwiki's zero-stdlib design rule.
- Privacy-first local-LLM implementations (kytmanov/obsidian-llm-wiki-local) resonate with users and align with llmwiki's no-telemetry positioning.
- Session history search tools (claude-history, search-sessions) are complementary, not competitive—[[llmwiki]]'s wiki compilation is additive to search-only workflows.

## Key Quotes

> "The 'Claude Code plugin' distribution mode is clean — ship as a plugin + a few .md files, zero runtime deps." — Identifies minimal viable distribution model for wiki skills.

> "This is the closest prior art. llmwiki inherits its directory layout and slash-command naming (`/wiki-*`)." — Establishes SamurAIGPT/llm-wiki-agent as the primary architectural influence.

> "Obsidian is a compelling viewer for many users — llmwiki should ship an Obsidian connector as an **optional** input/output, not the only path." — Design decision for multi-format viewer support.

> "There's a clean 'one-skill' positioning angle (minimal cognitive footprint) that resonates." — Validates lightweight distribution as a market position.

> "'Tool-portable memory' framing — 'one brain, every AI tool'." — Multi-agent portability pattern from remember-md/remember.

> "This is the 'full-stack' approach. llmwiki is explicitly the opposite — zero infra, all local." — Confirms llmwiki's strategic positioning against hosted alternatives.

## Connections

- [[llmwiki]] (entity) — the product this research informs; positioned as lightweight local-first alternative to heavy hosted/SaaS wikis.
  - fact: Inherits directory layout and slash-command naming from SamurAIGPT/llm-wiki-agent.
  - fact: Should support Obsidian as optional adapter, not sole viewer.

- [[Obsidian]] (entity) — note-taking application; compelling viewer for many users but should remain optional.
  - fact: Full Obsidian-lock (AgriciDaniel/claude-obsidian) limits addressable users.
  - fact: Writer/viewer split (Claude Code writer + Obsidian viewer) is a usable mental model.

- [[Claude Code]] (entity) — distribution channel; plugin mode achieves clean minimal distribution.
  - fact: Pure-markdown plugins (wiki-skills) + zero runtime deps is a viable entry point.

- [[Adapters]] (concept) — plugin/connector pattern; research validates optional multi-format strategy.
  - fact: Obsidian should be one adapter among many (privacy-first local LLM, session search backends).

- [[Knowledge Graph]] (concept) — visualization; SamurAIGPT's vis.js graph generation is prior art.
  - fact: Graph rendering is expected output for schema-aware wikis.

- [[Wiki Synthesis]] (concept) — core activity; prior art focuses on markdown ingestion; [[llmwiki]] adds session-transcript awareness.
  - fact: Session history search (claude-history, search-sessions) complements but does not replace wiki compilation.

- [[Static Site]] (concept) — HTML output; most markdown-first implementations lack static rendering; full-stack hosted solutions over-engineer for this.
  - fact: Local-first generation (no Node/S3) aligns with llmwiki's stdlib rule.

## Contradictions

None identified. The research corroborates [[llmwiki]]'s stated design principles (local-first, zero infrastructure, optional [[Obsidian]] support, [[Adapters|adapter pattern]]) against live competitive landscape.