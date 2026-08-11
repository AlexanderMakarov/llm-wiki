---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 3/3: P · Novel inventions for llmwiki)"
slug: feature-matrix-every-feature-across-the-15-prior-implementations-03
project: feature-matrix-every-feature-across-the-15-prior-implementations
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/feature-matrix.md"
content_sha256: 012d602c26d7c3726ae2881cf13271e1f2a2e172db2683c46811f0983ddefa05
---

> Part 3 of 3 of **Feature Matrix — Every Feature Across the 15 Prior Implementations** — P · Novel inventions for llmwiki.

## P · Novel inventions for llmwiki

These are features **no prior implementation has** that llmwiki will ship:

| # | Feature | Value | Rationale |
|---|---|---|---|
| P1 | **Session `.jsonl` → markdown adapter** | ⭐⭐⭐⭐⭐ | The entire reason llmwiki exists |
| P2 | **Cmd+K command palette** | ⭐⭐⭐⭐⭐ | Modern dev-tool UX standard |
| P3 | **Client-side search index + fuzzy matcher** | ⭐⭐⭐⭐⭐ | No dependencies, works offline, instant |
| P4 | **Pygments syntax highlighting at build** | ⭐⭐⭐⭐⭐ | Code blocks look professional |
| P5 | **Keyboard shortcuts** (`/`, `g h`, `j/k`) | ⭐⭐⭐⭐⭐ | Power-user UX |
| P6 | **Breadcrumbs + scroll-spy** | ⭐⭐⭐⭐ | Orient users in long sessions |
| P7 | **Collapsible tool-result sections** | ⭐⭐⭐⭐ | Session transcripts are verbose |
| P8 | **Sticky sessions-table header** | ⭐⭐⭐⭐ | 300-row tables need it |
| P9 | **Filter bar** on sessions table | ⭐⭐⭐⭐ | Project/date/model filters |
| P10 | **Live-session skip (`<60min`)** | ⭐⭐⭐⭐⭐ | Prevents reading mid-write files |
| P11 | **Adapter registry with schema version tracking** | ⭐⭐⭐⭐⭐ | Clean extensibility contract |
| P12 | **Redaction by default (username, keys, tokens, emails)** | ⭐⭐⭐⭐⭐ | No other impl does this |
| P13 | **Performance budget enforced in CI** | ⭐⭐⭐⭐ | 9s cold build, 0.4s no-op |
| P14 | **Hover-to-preview wikilinks** | ⭐⭐⭐⭐ | Obsidian-inspired navigation |
| P15 | **Self-demo via GitHub Pages on tag push** | ⭐⭐⭐⭐⭐ | Zero-effort marketing |

## Total feature count

| Category | Count | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
|---|---|---|---|---|---|---|
| A Core workflows | 10 | 3 | 3 | 3 | 1 | 0 |
| B Input adapters | 11 | 3 | 1 | 4 | 2 | 1 |
| C Page types | 12 | 6 | 3 | 2 | 1 | 0 |
| D Viewer | 22 | 6 | 13 | 3 | 2 | 0 |
| E Distribution | 8 | 3 | 2 | 2 | 2 | 0 |
| F Multi-agent | 7 | 4 | 2 | 1 | 0 | 0 |
| G Infrastructure | 10 | 3 | 2 | 3 | 1 | 1 |
| H Search | 6 | 2 | 0 | 3 | 1 | 0 |
| I Testing | 8 | 5 | 2 | 1 | 0 | 0 |
| J CI/CD | 7 | 2 | 2 | 3 | 0 | 0 |
| K Docs | 15 | 4 | 9 | 2 | 0 | 0 |
| L Config | 5 | 2 | 3 | 0 | 0 | 0 |
| M Privacy | 9 | 6 | 1 | 1 | 1 | 0 |
| N UX polish | 9 | 1 | 5 | 1 | 2 | 0 |
| O Operational | 7 | 3 | 2 | 1 | 0 | 0 |
| P Novel | 15 | 10 | 5 | 0 | 0 | 0 |
| **TOTAL** | **161** | **63** | **55** | **30** | **13** | **2** |

**63 features rated ⭐⭐⭐⭐⭐** are what make this a "god-level" build. They're all ship-in-v0.1 targets.
