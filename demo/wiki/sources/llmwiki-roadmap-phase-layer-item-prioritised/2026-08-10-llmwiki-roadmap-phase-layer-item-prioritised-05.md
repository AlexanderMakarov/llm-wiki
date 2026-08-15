---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 5/5: Summary by layer)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-roadmap-phase-layer-item-prioritised, moscow-prioritization, layer-based-architecture, work-breakdown-structure]
date: 2026-08-10
source_file: 
project: llmwiki-roadmap-phase-layer-item-prioritised
model: 
last_updated: 2026-08-11
---
## Summary

This page consolidates the llmwiki roadmap into 135 prioritized work items across 8 architectural layers (Raw, Wiki, Site, Viewer, Distribution, Schema, Adapters, CI/Ops) and 6 release phases spanning v0.1 through v1.0. v0.1 commits to 87 must-have items, with the remaining 44 explicitly classified as should, could, or won't in a MoSCoW prioritization framework. The execution sequence is designed to minimize rework: schema (L5) and adapter registry (L6) first, then converter (L0), builder (L2), viewer (L3), scripts (L4), tests (L7), and seed data (L1). Current work focuses on the HTML builder and JavaScript viewer components.

## Key Claims

- v0.1 release contains exactly 87 must-have items across all layers; the remaining 44 items (31 should, 11 could, 6 won't) are explicit roadmap for v0.2–v1.0, preventing silent scope creep.
- The optimal execution sequence minimizes rework by implementing dependencies in order: schema (L5) → adapters (L6) → converter (L0) → builder (L2) → viewer (L3) → scripts (L4) → tests (L7) → seed (L1).
- The 8-layer decomposition (Raw, Wiki, Site, Viewer, Distribution, Schema, Adapters, CI/Ops) isolates architectural concerns, allowing parallel work within layers and clear dependency ordering between them.
- v0.2 adds Obsidian bidirectional sync, new CLI commands, and the Claude Code plugin; v0.4 adds local LLM and web clipper; v1.0 locks the API with full documentation and production adapter test coverage.

## Key Quotes

> "When claiming an item as done, mark it ✅ in the Status column of tasks.md. When adding a new feature idea, add a row here first (with priority + layer) before writing code."

This establishes the working practice: the roadmap is a gate for all implementation work, ensuring no features bypass prioritization.

> "v0.1 ships with 87 Must-have items. Everything else is roadmap."

The explicit scope cap prevents unlimited scope creep during v0.1 execution.

## Connections

- [[llmwiki]] — this is the authoritative roadmap defining the project's execution path through v1.0
- [[Layer-Based Architecture]] — the 8-layer decomposition structures all 135 work items and defines build order

## Contradictions

None identified.