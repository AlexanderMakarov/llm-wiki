---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 2/3: G · Infrastructure)"
slug: feature-matrix-every-feature-across-the-15-prior-implementations-02
project: feature-matrix-every-feature-across-the-15-prior-implementations
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/feature-matrix.md"
content_sha256: 012d602c26d7c3726ae2881cf13271e1f2a2e172db2683c46811f0983ddefa05
---

> Part 2 of 3 of **Feature Matrix — Every Feature Across the 15 Prior Implementations** — G · Infrastructure.

## G · Infrastructure

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| G1 | Raw-file mtime tracker (idempotent sync) | ⭐⭐⭐⭐⭐ | hsuanguo, llmwiki state file | v0.1 |
| G2 | **File watcher (auto-resync on .jsonl change)** | ⭐⭐⭐⭐ | bitsofchris, kytmanov | v0.2 |
| G3 | Git ops integration (auto-commit wiki changes) | ⭐⭐⭐ | kytmanov | v0.2 |
| G4 | **MCP server (expose wiki as tools to agents)** | ⭐⭐⭐⭐⭐ | bitsofchris, lucasastorian | v0.2 |
| G5 | SQLite backend (structured queries) | ⭐⭐⭐ | bashiraziz | v0.3 |
| G6 | Supabase / Postgres backend | ⭐ | lucasastorian | won't |
| G7 | Sentry error tracking | ⭐ | lucasastorian | won't |
| G8 | SessionStart hook auto-sync | ⭐⭐⭐⭐⭐ | remember-md | v0.1 |
| G9 | UserPromptSubmit hook (contextual wiki injection) | ⭐⭐⭐ | remember-md | v0.2 |
| G10 | Live-session detection (skip `<60min` old) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |

## H · Search / discovery

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| H1 | **Client-side search index (JSON + fuzzy matcher)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| H2 | Server-side full-text (SQLite FTS5) | ⭐⭐⭐ | bashiraziz | v0.3 |
| H3 | Rerank results by relevance | ⭐⭐ | bitsofchris | v0.3 |
| H4 | Taxonomy / faceted filtering | ⭐⭐⭐ | bitsofchris | v0.2 |
| H5 | Backlinks (bidirectional `[[wikilinks]]`) | ⭐⭐⭐⭐⭐ | **None explicit** | v0.1 |
| H6 | Tag cloud / tag index | ⭐⭐⭐ | **None** | v0.2 |

## I · Testing & quality

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| I1 | Unit tests (pytest) | ⭐⭐⭐⭐⭐ | bitsofchris, kytmanov, hsuanguo, lucasastorian | v0.1 |
| I2 | Snapshot tests for adapters | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| I3 | Fixture-based end-to-end tests | ⭐⭐⭐⭐⭐ | bitsofchris, kytmanov | v0.1 |
| I4 | Eval framework (LLM-judged wiki quality) | ⭐⭐⭐ | xoai | v0.3 |
| I5 | Link checker (CI) | ⭐⭐⭐⭐ | **None explicit** | v0.1 |
| I6 | **Gitleaks secret scanning in CI** | ⭐⭐⭐⭐⭐ | sinzin91 | v0.1 |
| I7 | Privacy check (grep for real PII in fixtures) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| I8 | Performance budget enforcement | ⭐⭐⭐⭐ | **None** | v0.1 |

## J · CI / CD

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| J1 | `ci.yml` — lint + test on every PR | ⭐⭐⭐⭐⭐ | kytmanov, sinzin91 | v0.1 |
| J2 | `pages.yml` — deploy GitHub Pages demo | ⭐⭐⭐⭐⭐ | xoai | v0.1 |
| J3 | `release.yml` — tag-push releases | ⭐⭐⭐⭐ | sinzin91, kytmanov | v0.2 |
| J4 | PR-merge auto-release | ⭐⭐⭐ | sinzin91 | v0.2 |
| J5 | Version check script | ⭐⭐⭐ | Ss1024sS | v0.2 |
| J6 | Upgrade flow (`./upgrade.sh`) | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| J7 | Dependabot (even with no deps — track GHA versions) | ⭐⭐⭐ | many | v0.1 |

## K · Documentation

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| K1 | `README.md` with install + demo | ⭐⭐⭐⭐⭐ | All | v0.1 |
| K2 | `SETUP-GUIDE.md` with per-OS instructions | ⭐⭐⭐⭐ | bashiraziz, Ss1024sS | v0.1 |
| K3 | `QUICK-REFERENCE.md` — one-page cheat sheet | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K4 | `CHANGELOG.md` | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| K5 | Per-version release notes | ⭐⭐⭐ | Ss1024sS | v0.2 |
| K6 | `ARCHITECTURE.md` formal architecture | ⭐⭐⭐⭐⭐ | bitsofchris, sinzin91 | v0.1 |
| K7 | Knowledge-system playbook | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| K8 | Ingest-pipeline doc | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| K9 | MCP server doc | ⭐⭐⭐ | bitsofchris | v0.2 |
| K10 | Windows-specific setup doc | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K11 | Obsidian integration doc | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K12 | Benchmarks doc | ⭐⭐⭐⭐ | sinzin91 | v0.1 |
| K13 | Phased plans (m0/m1/m2/phase2/phase3) | ⭐⭐⭐⭐⭐ | bitsofchris | v0.1 (= `_progress.md`) |
| K14 | Domain examples (personal/research/business) | ⭐⭐⭐⭐ | bashiraziz | v0.2 |
| K15 | Use-case examples (solo/team/multi) | ⭐⭐⭐⭐ | bashiraziz | v0.2 |

## L · Configuration

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| L1 | JSON config with defaults | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| L2 | `config.defaults.json` + user override | ⭐⭐⭐⭐ | remember-md | v0.1 |
| L3 | Environment variable support (`LLMWIKI_*`) | ⭐⭐⭐⭐ | — | v0.1 |
| L4 | Plugin manifest (`.claude-plugin/plugin.json`) | ⭐⭐⭐⭐⭐ | kfchou, sinzin91, remember-md | v0.2 |
| L5 | Claude Code marketplace file | ⭐⭐⭐⭐ | kfchou, sinzin91 | v0.2 |

## M · Privacy & security

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| M1 | **Username redaction** (`/Users/you/` → `/Users/USER/`) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M2 | **API key / token / password regex redaction** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M3 | **Email redaction** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M4 | **Gitleaks secret scan in CI** | ⭐⭐⭐⭐⭐ | sinzin91 | v0.1 |
| M5 | **Localhost-only binding by default** | ⭐⭐⭐⭐⭐ | **None explicit** | v0.1 |
| M6 | **No telemetry (hard rule)** | ⭐⭐⭐⭐⭐ | lightweight ones imply | v0.1 |
| M7 | **Local LLM option (Ollama)** | ⭐⭐⭐ | kytmanov | v0.3 |
| M8 | **`.llmwikiignore`** — skip files from sync | ⭐⭐⭐⭐ | **None** | v0.1 |
| M9 | Encrypt raw/ at rest | ⭐⭐ | — | v0.3 |

## N · UX polish

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| N1 | Inter + JetBrains Mono typography | ⭐⭐⭐⭐⭐ | — | v0.1 |
| N2 | Proper focus rings (a11y) | ⭐⭐⭐⭐ | — | v0.1 |
| N3 | Smooth scroll | ⭐⭐⭐⭐ | — | v0.1 |
| N4 | Anchor scroll-margin-top | ⭐⭐⭐⭐ | — | v0.1 |
| N5 | Motion-reduced option (`prefers-reduced-motion`) | ⭐⭐⭐ | — | v0.1 |
| N6 | Empty states (no sessions, no results) | ⭐⭐⭐⭐ | — | v0.1 |
| N7 | Loading states | ⭐⭐ | — | won't (static) |
| N8 | Toast notifications on copy success | ⭐⭐⭐⭐ | — | v0.1 |
| N9 | Page transitions | ⭐⭐ | — | v0.2 |

## O · Operational features

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| O1 | Contradiction tracking in wiki pages | ⭐⭐⭐⭐⭐ | SamurAIGPT, our CLAUDE.md | v0.1 |
| O2 | Stale-page detection (lint) | ⭐⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| O3 | Version upgrade flow | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| O4 | Cross-project wiring (multi-wiki from one repo) | ⭐⭐⭐ | bashiraziz | v0.3 |
| O5 | Wiki changelog (auto-generated from `log.md`) | ⭐⭐⭐⭐ | — | v0.1 |
| O6 | Wiki backup / export | ⭐⭐⭐ | — | v0.2 |
| O7 | Dry-run mode everywhere | ⭐⭐⭐⭐⭐ | — | v0.1 |
