---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 3/5)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-roadmap-phase-layer-item-prioritised, architecture-layers, feature-roadmap, prioritization]
date: 2026-08-10
source_file: 
project: llmwiki-roadmap-phase-layer-item-prioritised
model: 
last_updated: 2026-08-11
---
## Summary

Part 3 of a 5-part prioritized roadmap for [[llmwiki]], organized as a systematic 6-layer architecture spanning data processing (L0) through Python packaging (L6). This excerpt details medium-priority features across: core session redaction and state management (L0); workflow templates and page schemas for ingest/query/lint (L1); HTML builder and frontend infrastructure (L2); client-side UI features including search, keyboard shortcuts, dark mode (L3); CLI shell integration (L4); documentation and steering (L5); and Python adapter structure (L6).

## Key Claims

- llmwiki architecture comprises 6 discrete layers: L0 (data/adapter layer), L1 (workflow templates and schemas), L2 (HTML/static builder), L3 (client-side UI), L4 (CLI/shell), L5 (documentation/meta), L6 (Python packages)
- L0 core features include regex-based PII redaction, idempotent mtime state files (`.llmwiki-state.json`), live-session detection (skip sessions <60 min old), and sub-agent file rendering
- L1 defines three core workflows—ingest, query, lint—following the [[Karpathy Framework]] 10-step pattern, with separate page templates for sources, entities, concepts, and syntheses
- L3 client-side feature set includes command palette, global fuzzy search, keyboard shortcuts (`/`, `Esc`, `g h`, `g p`, `g s`, `j/k`), dark mode with localStorage, and copy-to-clipboard buttons on code and session pages
- Contradiction tracking is treated as a first-class rule (M-L1-12): "Never silently overwrite, record both claims"

## Key Quotes

> "Karpathy 10-step flow" — ingest/query/lint workflows are explicitly specified to follow the [[Karpathy Framework]] pattern (M-L1-01, M-L1-02, M-L1-03)

> "Never silently overwrite, record both claims" — contradiction handling is encoded as architectural requirement, ensuring conflicting wiki entries are preserved (M-L1-12)

> "Inter + JetBrains Mono + purple accent" — deliberate typographic and color choices indicate cohesive visual identity (M-L2-01)

## Connections

- [[llmwiki]] — the entire project being planned and architected
- [[Karpathy Framework]] — ingest/query/lint workflows explicitly adopt the 10-step agent pattern

## Contradictions

None identified (early-phase roadmap document).