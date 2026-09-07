---
title: "Phase 1.25 — Research Report (part 2/3: Per-repo analysis)"
type: source
tags: [wiki-add, raw-doc, session-transcript, phase-1-25-research-report, competitive-analysis, transcript-ingestion, prior-art, obsidian-optional, distribution-models]
date: 2026-08-10
source_file: 
project: phase-1-25-research-report
model: 
last_updated: 2026-09-07
---
## Summary

Part 2 of Phase 1.25 research report, analyzing 20+ existing LLM wiki projects across pure-markdown, Python-hybrid, Obsidian-coupled, heavy-infrastructure, and session-browser categories. The analysis identifies critical gaps in competing tools—most notably the lack of session-transcript ingestion and static HTML output—and design lessons that directly inform [[llmwiki]]'s architecture: lightweight distribution via Claude Code plugins and templates, adapter-based multi-agent portability, optional (not mandatory) [[Obsidian]] integration, and strict adherence to local-only, zero-infrastructure execution.

## Key Claims

- SamurAIGPT's llm-wiki-agent is the closest prior art; [[llmwiki]] inherits its directory layout and `/wiki-*` slash-command naming pattern
- Session-transcript ingestion is a major feature gap across competing tools; most assume manual "drop markdown in `raw/`" input
- Static HTML output + multi-agent support are rare among pure-markdown approaches
- The Claude Code plugin distribution model with minimal dependencies is clean and viable
- [[Obsidian]] integration works best as an optional input/output layer, not as a mandatory lock-in requirement
- Heavy Python/hosted approaches (e.g., lucasastorian/llmwiki with 47 Python files + Supabase + S3 infrastructure) violate [[llmwiki]]'s zero-infrastructure philosophy
- Search-only session browsers ([[claude-history]], search-sessions) are complementary tools, not competitors; could serve as optional search backends

## Key Quotes

> "The 'Claude Code plugin' distribution mode is clean — ship as a plugin + a few .md files, zero runtime deps." — on why minimal-dependency distribution resonates.

> "This is the closest prior art. llmwiki inherits its directory layout and slash-command naming (`/wiki-*`)." — on SamurAIGPT/llm-wiki-agent's direct influence on [[llmwiki]] design.

> "100% Obsidian-locked. If you don't use Obsidian, this is useless… llmwiki should ship an Obsidian connector as an **optional** input/output, not the only path." — on avoiding vendor lock-in through optional integrations.

## Connections

- [[llmwiki]] (project) — this Phase 1.25 research directly informs [[llmwiki]]'s design decisions, positioning, and architecture
  - fact: Session-transcript ingestion is identified as a critical differentiator vs. 20+ existing tools.
  - fact: Local-only + zero-infrastructure rules are positioned explicitly against hosted approaches like lucasastorian/llmwiki.

- [[Adapters]] (concept) — the report identifies multi-agent portability as a key value proposition; [[Adapters]] are the mechanism

- [[Static Site]] (concept) — HTML rendering is identified as a major gap in most competitors
  - fact: Pure-markdown projects (wiki-skills, karpathy-llm-wiki, llm-wiki-template) lack HTML output; SamurAIGPT's vis.js graph is the closest precedent.

- [[Knowledge Graph]] (concept) — vis.js visualization sets a prior-art benchmark

- [[Obsidian]] (product) — the report examines multiple Obsidian-coupled wikis and recommends integration as optional, not mandatory

- [[Wiki Synthesis]] (concept) — core problem space; the report categorizes competing solutions across architectural trade-offs
  - fact: Pure-markdown approaches are minimal but lack HTML output; markdown+Python hybrids add runtime dependencies; hosted approaches sacrifice simplicity for features.

- [[Wikilinks]] (concept) — session-browser tools (claude-history, search-sessions) handle search; [[llmwiki]]'s wiki layer adds persistent cross-referenced structure

## Contradictions

None identified. This is exploratory research documenting existing tools' strengths, gaps, and design patterns—not contradicting prior [[llmwiki]] documentation.