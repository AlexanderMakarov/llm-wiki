---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 5/5: Summary by layer)"
slug: llmwiki-roadmap-phase-layer-item-prioritised-05
project: llmwiki-roadmap-phase-layer-item-prioritised
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/roadmap.md"
content_sha256: d84808a92adbc0c1aac2eb99e3b5bed4e5cee5f11a556cc320b99ac09ad8a6b1
---

> Part 5 of 5 of **llmwiki Roadmap — Phase × Layer × Item, prioritised** — Summary by layer.

## Summary by layer

| Layer | Must | Should | Could | Won't | Total |
|---|:-:|:-:|:-:|:-:|:-:|
| L0 Raw | 6 | 3 | 0 | 1 | 10 |
| L1 Wiki | 12 | 6 | 2 | 0 | 20 |
| L2 Site | 11 | 4 | 1 | 1 | 17 |
| L3 Viewer | 15 | 4 | 1 | 1 | 21 |
| L4 Distribution | 8 | 3 | 1 | 1 | 13 |
| L5 Schema/Docs | 18 | 4 | 1 | 0 | 23 |
| L6 Adapters | 7 | 4 | 3 | 0 | 14 |
| L7 CI/Ops | 10 | 3 | 2 | 2 | 17 |
| **TOTAL** | **87** | **31** | **11** | **6** | **135** |

**v0.1 ships with 87 Must-have items.** Everything else is roadmap.

## Summary by phase

| Phase | Focus | Items |
|---|---|---|
| v0.1.0 | Claude Code adapter + god-level UI + schema + CI | All 87 M rows |
| v0.1.x | Bug fixes, docs polish, perf tweaks | From feedback |
| v0.2.0 | Obsidian (bidirectional) + `/wiki-update` + `/wiki-graph` + Claude Code plugin + Cursor adapter | S rows in L1/L2/L3/L6 |
| v0.3.0 | Codex CLI full + Gemini CLI + PDF + Tag cloud + PyPI | Remaining S rows |
| v0.4.0 | Local LLM (Ollama) + Web clipper + Docker | C rows |
| v1.0.0 | Stabilised schema + production adapter test suite + full docs i18n | Lock the API |

## Execution sequence

Because everything in the Must list is already scoped, the execution order that minimises rework is:

1. **L5 first** — Schema files (CLAUDE.md, AGENTS.md, docs, tasks, progress). Done, validates the plan.
2. **L6 registry + base** — Adapter interface. Done.
3. **L0 converter** — Claude Code adapter + redaction + state. Done.
4. **L2 builder** — God-level HTML. **← current work**
5. **L3 viewer JS** — Command palette, search, shortcuts, copy buttons. **← current work**
6. **L4 scripts** — Shell + batch wrappers around the CLI.
7. **L7 tests** — Fixtures, snapshot tests, privacy grep, CI workflows.
8. **L1 seed** — `/wiki-init` seeds + sample ingest for the self-demo.

## How to use this document

- When claiming an item as done, mark it ✅ in the **Status** column of `tasks.md`.
- When adding a new feature idea, add a row here first (with priority + layer) before writing code.
- When cutting scope, move from M → S, not M → delete. Nothing gets silently dropped.
