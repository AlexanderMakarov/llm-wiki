---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 1/5)"
slug: llmwiki-roadmap-phase-layer-item-prioritised-01
project: llmwiki-roadmap-phase-layer-item-prioritised
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/roadmap.md"
content_sha256: d84808a92adbc0c1aac2eb99e3b5bed4e5cee5f11a556cc320b99ac09ad8a6b1
---

> Part 1 of 5 of **llmwiki Roadmap — Phase × Layer × Item, prioritised**.

# llmwiki Roadmap — Phase × Layer × Item, prioritised

**Last updated:** 2026-04-08

This document is the master plan. It slices the [feature matrix](feature-matrix.md) three ways so you can see:

- **By layer** — what you're building in each of the 8 architectural layers
- **By phase** — what ships in v0.1 vs v0.2 vs later
- **By priority** — MoSCoW ordering for execution sequence

## The 8 layers

Every feature belongs to exactly one architectural layer:

| Layer | What lives here | Owner |
|---|---|---|
| L0 Raw | Immutable converted markdown under `raw/` | Converter |
| L1 Wiki | LLM-maintained pages under `wiki/` | Agent (via slash commands) |
| L2 Site | Generated HTML under `site/` | Builder |
| L3 Viewer | HTTP server, search, keyboard shortcuts | Browser-side JS |
| L4 Distribution | Scripts, plugins, packaging | Setup/install |
| L5 Schema | `CLAUDE.md`, `AGENTS.md`, steering rules | Docs |
| L6 Adapters | Session-store parsers (Claude, Codex, Obsidian…) | Adapter registry |
| L7 CI/Ops | Tests, workflows, release automation | GitHub Actions |

## MoSCoW priority

| Priority | Meaning | When to ship |
|---|---|---|
| **M** = Must | v0.1 ships without this → the product fails | v0.1.0 |
| **S** = Should | Strong user value but v0.1 can survive without | v0.1.1 or v0.2.0 |
| **C** = Could | Nice to have; ship when a contributor or issue demands | v0.3+ |
| **W** = Won't | Considered and rejected for scope / philosophy reasons | Never in v1.x |
