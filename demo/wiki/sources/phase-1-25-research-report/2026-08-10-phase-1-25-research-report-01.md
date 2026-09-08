---
title: "Phase 1.25 — Research Report (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, phase-1-25-research-report, prior-art-analysis, implementation-clusters, llmwiki-differentiation]
date: 2026-08-10
source_file: 
project: phase-1-25-research-report
model: 
last_updated: 2026-09-07
---
## Summary

Phase 1.25 Research analyzed 15 reference implementations of LLM wikis cloned from Karpathy's gist and GitHub to identify the "10x gap" llmwiki targets. The implementations clustered into five categories: pure-markdown skills, markdown-first + light Python, Obsidian-coupled, heavy Python/hosted, and session browsers. The analysis shows llmwiki's positioning: combining the best of markdown-first + static site generation + multi-agent support + session-transcript [[Adapters]], while staying lightweight and avoiding hosted complexity.

## Key Claims

- 15 reference implementations exist in four distinct architectural clusters for LLM wiki building.
- llmwiki differentiates by supporting multiple input [[Adapters]] (including session transcripts) rather than a single primary view (e.g., Obsidian-only or hosted-only).
- Pure-markdown and light-Python approaches are the closest prior art; llmwiki extends them with session-transcript ingestion and beautiful [[Static Site]] output.
- Hosted, heavy-Python solutions (with databases and MCP) violate llmwiki's stdlib-first design principle and are not part of the target architecture.
- Session browsers (raw `.jsonl` search tools) are complementary to wiki building, not competitors — they operate at a different layer.

## Key Quotes

> "This document is the source of truth for prior-art analysis and the 10x gap that llmwiki targets."

This establishes the research phase as foundational for understanding llmwiki's design rationale and competitive positioning.

## Connections

- [[llmwiki]] (project) — the subject being differentiated through prior-art analysis; aims to synthesize strengths of multiple existing approaches.
  - fact: llmwiki combines markdown-first schema + static HTML generation + session-transcript adapter + multi-agent support.
- [[Obsidian]] (tool) — one architectural pattern observed in prior art; llmwiki treats it as an optional input [[Adapters|adapter]] rather than the only view.
  - fact: Projects like `AgriciDaniel/claude-obsidian` and `remember-md/remember` couple the wiki to Obsidian; llmwiki decouples.
- [[Adapters]] (concept) — a key differentiator; llmwiki's multi-source design contrasts with single-channel implementations.
- [[Static Site]] (concept) — llmwiki's output target, aligned with the markdown-first + light-Python cluster but with enhanced generation.
- [[GitHub Pages]] (platform) — likely deployment target for llmwiki's generated static wikis.
