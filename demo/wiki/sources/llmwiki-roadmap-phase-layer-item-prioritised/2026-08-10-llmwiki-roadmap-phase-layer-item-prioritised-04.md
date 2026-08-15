---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 4/5)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-roadmap-phase-layer-item-prioritised, mcp-server, performance-budgets, feature-prioritization, github-pages]
date: 2026-08-10
source_file: 
project: llmwiki-roadmap-phase-layer-item-prioritised
model: 
last_updated: 2026-08-11
---
## Summary

The llmwiki roadmap (part 4 of 5) organizes features using a Phase × Layer × Item matrix, where Phase ∈ {M=Must, S=Should, C=Could, W=Won't do} and Layer ∈ {L0–L7} spanning adapters through documentation and infrastructure. Major prioritization decisions include promoting MCP server and Claude Code plugin packaging from Should to Must (2026-04-08), declining comparison and question page types (2026-08-09, #109 for lack of producer), and establishing hard performance budgets (build <15s, HTML <50MB). The roadmap reflects privacy-first (no telemetry) and stdlib-first (no external backends) architectural constraints.

## Key Claims

- llmwiki uses a two-dimensional Phase × Layer prioritization system with Layer subdivisions L0–L7 covering core adapters (L0), CLI commands (L1), UI/UX (L2–L3), IDE integration (L4), documentation (L5), adapter ecosystem (L6), and testing/deployment (L7)
- MCP server and Claude Code plugin packaging were both promoted from Should to Must on 2026-04-08
- Comparison and Question page types were explicitly declined on 2026-08-09 (#109) citing "no producer, no perceived value"
- Six CLI commands are Must-have: `wiki-sync`, `wiki-ingest`, `wiki-query`, `wiki-lint`, `wiki-build`, `wiki-serve`
- Planned adapters span multiple IDEs/editors: Claude Code, Obsidian, Cursor, Codex CLI, Gemini CLI
- Performance is constrained: build time <15s, total HTML output <50MB
- Privacy and technology choices are firm constraints: Sentry telemetry and Supabase/Postgres backends are marked Won't-do

## Key Quotes

> M | L4 | M-L4-12 | **MCP server** exposing `wiki_query`, `wiki_ingest`, `wiki_search`, `wiki_lint` tools | Promoted from S → M on 2026-04-08

MCP integration is now essential to the product, not an optional enhancement.

> S | L1 | S-L1-05 | ~~Comparison page type~~ | Declined 2026-08-09 (#109) — no producer, no perceived value

Shows explicit decision discipline: features decline when motivation and use-case are absent.

> W | L7 | W-L7-01 | Sentry / telemetry | Privacy rule  

Privacy is a hard constraint, not deferred to future consideration.

> M | L7 | M-L7-09 | Performance budget check — build time `<15s`, HTML `<50MB`

Quantified, CI-enforced performance targets.

## Connections

- [[llmwiki]] — the project being roadmapped
- [[Model Context Protocol]] — MCP server elevated to Must-have tier; core integration platform
- [[Claude Code]] — plugin packaging is Must-have; extends into Anthropic's editor ecosystem
- [[GitHub Pages]] — deployment target for built wiki via tag-push workflow

## Contradictions

None identified. This document establishes project priorities rather than contradicting prior decisions.