---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 1/5)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-roadmap-phase-layer-item-prioritised, moscow-prioritization, architectural-layers, feature-planning]
date: 2026-08-10
source_file: 
project: llmwiki-roadmap-phase-layer-item-prioritised
model: 
last_updated: 2026-08-11
---
## Summary

This document establishes the master roadmap framework for llm-wiki, organizing features across three dimensions: 8 architectural layers (Raw, Wiki, Site, Viewer, Distribution, Schema, Adapters, CI/Ops), release phases (v0.1 through v0.3+), and MoSCoW priorities (Must/Should/Could/Won't). The framework assigns each feature to exactly one layer with clear ownership, then maps execution priority to shipping milestones. This is part 1 of a 5-part roadmap series.

## Key Claims

- llm-wiki's architecture consists of exactly 8 layers; each feature belongs to precisely one layer with a single owner
- MoSCoW categorization maps directly to shipping milestones: Must features are v0.1 blockers; Should are v0.1.1–v0.2; Could are v0.3+; Won't features are permanently out of scope for v1.x
- The converter (L0), agent (L1), and builder (L2) form the core content pipeline
- Schema documentation (L5), adapter registry (L6), and CI/Ops automation (L7) are separate concerns from the active feature layers

## Key Quotes

> "Every feature belongs to exactly one architectural layer" — the organizing principle for clean separation of concerns and single ownership

> "v0.1 ships without this → the product fails" — the definition of Must-priority features that gate the MVP

## Connections

- [[Feature Matrix]] — the source matrix being sliced by layer, phase, and priority in this roadmap