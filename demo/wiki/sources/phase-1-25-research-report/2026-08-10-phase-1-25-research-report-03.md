---
title: "Phase 1.25 — Research Report (part 3/3: The 10x gap (feature matrix))"
type: source
tags: [wiki-add, raw-doc, session-transcript, phase-1-25-research-report, competitive-analysis, feature-matrix, privacy-redaction, build-performance]
date: 2026-08-10
source_file: 
project: phase-1-25-research-report
model: 
last_updated: 2026-09-07
---
## Summary

This research report establishes llmwiki's competitive positioning by analyzing 15 reference implementations across 15 feature dimensions. The "10x gap" feature matrix identifies key differentiators: beautiful static HTML viewer with client-side global search, build-time redaction of PII, sub-15-second build times, multi-adapter architecture, and stdlib-first implementation. Six product decisions emerge from the research: prioritize stdlib approach, ship [[Obsidian]] adapter in v0.1, lead with the HTML viewer as the hero feature, maintain slash command compatibility with existing tools, adopt Karpathy's three-layer directory structure exactly, and establish build-time redaction as non-negotiable.

## Key Claims

- llmwiki's "10x gap" spans 15 feature categories where it matches or exceeds all 15 reference implementations, including `.jsonl` transcript ingestion, multi-agent adapter patterns, static HTML output, global client-side search, syntax highlighting, live-session detection, incremental idempotent sync, and build performance
- None of the 15 reference implementations feature a beautiful static HTML viewer with client-side search indexing (Cmd+K) and syntax highlighting—making this [[llmwiki]]'s most visible competitive advantage
- Build-time redaction of usernames, API keys, tokens, and emails is established as non-negotiable; no reference implementations perform this redaction automatically, creating a unique PII security advantage
- [[Obsidian]] integration is critical infrastructure: four of 15 reference implementations rely on it, justifying it as a v0.1 priority shipped as both input and output adapter
- [[llmwiki]] achieves consistent build times under 15 seconds for 300 sessions (measured at 9 seconds), faster than most competitors
- Stdlib-first architecture (pure Python + `markdown`, no database, no MCP, no Node.js) differentiates [[llmwiki]] from full-stack approaches like lucasastorian/llmwiki

## Key Quotes

> "Beautiful static HTML viewer — god-level UI" — the [[Static Site]] viewer positioned as [[llmwiki]]'s most visible competitive advantage and hero feature for marketing

> "Build-time redaction is non-negotiable — none of the reference implementations do this, and session transcripts leak PII by default." — establishes privacy protection as a core principle distinguishing [[llmwiki]] from all competitors

> "Four of 15 reference implementations use Obsidian — clearly important to users." — rationale for prioritizing [[Obsidian]] as both input and output adapter in v0.1 release

## Connections

- [[llmwiki]] (product) — core subject of competitive positioning research across 15 reference implementations
  - fact: 10x feature gap identified across 15 dimensions; none of the reference implementations match llmwiki on all fronts
  - fact: Six key product decisions directly informed by the research: stdlib-first, [[Obsidian]] adapter, HTML viewer as hero, slash command compatibility, Karpathy's structure, and build-time redaction
  - fact: Shipped as both input **and** output adapter (unique among reference implementations)
- [[Static Site]] (feature) — identified as [[llmwiki]]'s single most visible 10x advantage
  - fact: Beautiful HTML viewer with global search and syntax highlighting differentiates from all 15 competitors
  - fact: Positioned as the primary hero feature for external visibility and marketing
- [[Adapters]] (architectural pattern) — multi-adapter architecture identified as novel capability not present in reference set
  - fact: Slash command compatibility with SamurAIGPT/llm-wiki-agent and kfchou/wiki-skills enables user switching between tools
- [[Redaction by Default]] (privacy principle) — established as [[llmwiki]]'s non-negotiable differentiator and security advantage
  - fact: Directly addresses critical PII leakage vulnerability present in all competitor implementations