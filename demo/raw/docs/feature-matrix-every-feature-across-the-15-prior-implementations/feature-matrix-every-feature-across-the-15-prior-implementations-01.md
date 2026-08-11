---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 1/3)"
slug: feature-matrix-every-feature-across-the-15-prior-implementations-01
project: feature-matrix-every-feature-across-the-15-prior-implementations
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/feature-matrix.md"
content_sha256: 012d602c26d7c3726ae2881cf13271e1f2a2e172db2683c46811f0983ddefa05
---

> Part 1 of 3 of **Feature Matrix — Every Feature Across the 15 Prior Implementations**.

# Feature Matrix — Every Feature Across the 15 Prior Implementations

**Method:** Cloned and inspected every referenced repo. Listed every feature I found in any of them, rated each by target value to llmwiki (1–5), and marked which ones are already present in at least one reference implementation vs. which are a net-new invention for llmwiki.

**Value legend:**

| Rating | Meaning |
|---|---|
| ⭐⭐⭐⭐⭐ | God-level — killer feature, llmwiki ships without it is pointless |
| ⭐⭐⭐⭐ | Strong must-have — ship in v0.1 |
| ⭐⭐⭐ | Should-have — ship in v0.2 or v0.3 |
| ⭐⭐ | Could-have — ship when there's demand |
| ⭐ | Won't-have — researched and rejected |

## A · Core wiki workflows

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| A1 | `/wiki-ingest` — read source → write wiki page | ⭐⭐⭐⭐⭐ | SamurAIGPT, kfchou, bashiraziz, Ss1024sS, hsuanguo, louiswang524 | v0.1 |
| A2 | `/wiki-query` — answer questions with citations | ⭐⭐⭐⭐⭐ | Same as above | v0.1 |
| A3 | `/wiki-lint` — orphans / contradictions / stale | ⭐⭐⭐⭐⭐ | Same as above | v0.1 |
| A4 | `/wiki-init` — scaffold empty wiki | ⭐⭐⭐⭐ | kfchou, hsuanguo | v0.1 |
| A5 | `/wiki-update` — update existing page without full re-ingest | ⭐⭐⭐ | kfchou, hsuanguo | v0.2 |
| A6 | `/wiki-graph` — knowledge graph (networkx/vis.js) | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| A7 | `/wiki-compile` — multi-step pipeline (plan → write → validate) | ⭐⭐⭐ | kytmanov, lucasastorian | v0.3 |
| A8 | `/wiki-reflect` — self-reflection over the whole wiki | ⭐⭐⭐ | louiswang524 | v0.2 |
| A9 | `/wiki-merge` — merge two wikis / vaults | ⭐⭐ | louiswang524 | v0.3 |
| A10 | `/wiki-archive` — move stale entries to archive | ⭐⭐⭐ | Astro-Han | v0.2 |

## B · Input adapters (data sources)

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| B1 | **Claude Code `.jsonl` adapter** (killer feature) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| B2 | **Codex CLI adapter** | ⭐⭐⭐⭐⭐ | bashiraziz (stub), Ss1024sS (script only) | v0.1 stub, v0.2 full |
| B3 | **Obsidian vault adapter** (input mode) | ⭐⭐⭐⭐ | AgriciDaniel, louiswang524, kytmanov, remember-md | v0.1 |
| B4 | Generic markdown (drop in `raw/`) | ⭐⭐⭐⭐ | All | v0.1 |
| B5 | Cursor adapter | ⭐⭐⭐ | bashiraziz | v0.2 |
| B6 | Gemini CLI adapter | ⭐⭐⭐ | SamurAIGPT (schema only) | v0.3 |
| B7 | OpenCode/OpenClaw adapter | ⭐⭐⭐ | remember-md, sinzin91 | v0.3 |
| B8 | PDF ingestion | ⭐⭐⭐ | lucasastorian | v0.3 |
| B9 | URL / web-clipper ingestion | ⭐⭐ | kytmanov | v0.4 |
| B10 | Image ingestion (screenshots, diagrams) | ⭐⭐ | louiswang524 (mentioned) | v0.4 |
| B11 | Slack / Discord export | ⭐ | — | won't |

## C · Page types / templates

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| C1 | Source page (`wiki/sources/`) | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C2 | Entity page (`wiki/entities/`) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| C3 | Concept page (`wiki/concepts/`) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| C4 | Synthesis page (`wiki/syntheses/`) | ⭐⭐⭐⭐ | SamurAIGPT, kfchou | v0.1 |
| C5 | **Comparison page** (side-by-side diff of 2+ entities) | ⭐⭐⭐⭐ | AgriciDaniel | v0.2 |
| C6 | **Question page** (open questions as first-class entries) | ⭐⭐⭐⭐ | AgriciDaniel | v0.2 |
| C7 | Archive page (demoted / deprecated entries) | ⭐⭐⭐ | Astro-Han | v0.2 |
| C8 | Insight page | ⭐⭐ | hsuanguo | v0.3 |
| C9 | Summary page | ⭐⭐⭐ | hsuanguo | v0.2 |
| C10 | `index.md` catalog | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C11 | `overview.md` living synthesis | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C12 | `log.md` append-only log | ⭐⭐⭐⭐⭐ | All | v0.1 |

## D · Output / viewer

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| D1 | **Static HTML site (no deps, no auth)** | ⭐⭐⭐⭐⭐ | xoai (basic), lucasastorian (auth-walled) | v0.1 |
| D2 | **Cmd+K command palette** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D3 | **Global client-side search (pre-built index)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D4 | **Syntax highlighting (Pygments)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D5 | **Dark mode toggle with system preference** | ⭐⭐⭐⭐⭐ | lucasastorian web only | v0.1 |
| D6 | **Keyboard shortcuts** (`/`, `g h`, `j/k`) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D7 | **Breadcrumbs** on session pages | ⭐⭐⭐⭐ | **None** | v0.1 |
| D8 | **Collapsible tool-result sections** | ⭐⭐⭐⭐ | **None** | v0.1 |
| D9 | **Reading-progress bar on long pages** | ⭐⭐⭐⭐ | **None** | v0.1 |
| D10 | **Sticky table headers** on sessions index | ⭐⭐⭐⭐ | **None** | v0.1 |
| D11 | **Mobile responsive** | ⭐⭐⭐⭐ | lucasastorian web | v0.1 |
| D12 | **Print-friendly CSS** | ⭐⭐⭐ | **None** | v0.1 |
| D13 | Copy-as-markdown button on every page | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D14 | Copy-code button on every `<pre>` | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D15 | Download-source-md button | ⭐⭐⭐⭐ | **None** | v0.1 |
| D16 | Anchor links on every heading | ⭐⭐⭐⭐ | SamurAIGPT, others | v0.1 |
| D17 | Knowledge graph view (vis.js) | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| D18 | Obsidian vault as viewer (export mode) | ⭐⭐⭐⭐ | AgriciDaniel, louiswang524 | v0.1 (export), v0.2 (bidirectional) |
| D19 | TUI browser | ⭐⭐ | raine | won't (use their tool) |
| D20 | Timeline view of sessions | ⭐⭐⭐ | **None** | v0.2 |
| D21 | Filter bar on sessions table (project, date, model) | ⭐⭐⭐⭐ | **None** | v0.1 |
| D22 | Hover-to-preview wikilinks (like Obsidian Page Preview) | ⭐⭐⭐⭐ | **None** | v0.2 |

## E · Distribution

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| E1 | `git clone + ./setup.sh` (macOS/Linux) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| E2 | `git clone + setup.bat` (Windows) | ⭐⭐⭐⭐⭐ | Few | v0.1 |
| E3 | `pip install -e .` local mode | ⭐⭐⭐⭐ | hsuanguo | v0.1 |
| E4 | **Claude Code plugin** (marketplace install) | ⭐⭐⭐⭐⭐ | kfchou, sinzin91, remember-md | v0.2 |
| E5 | Homebrew formula | ⭐⭐⭐ | raine (Go) | v0.3 |
| E6 | Precompiled single binary (Go/Rust?) | ⭐⭐ | sinzin91 (Go) | won't (Python) |
| E7 | `pip install llm-notebook` on PyPI | ⭐⭐⭐⭐ | lucasastorian | v0.3 |
| E8 | Docker image | ⭐⭐ | — | v0.4 |

## F · Multi-agent support

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| F1 | `CLAUDE.md` schema | ⭐⭐⭐⭐⭐ | All | v0.1 |
| F2 | `AGENTS.md` schema (Codex, OpenCode) | ⭐⭐⭐⭐⭐ | SamurAIGPT, Ss1024sS, bashiraziz | v0.1 |
| F3 | `GEMINI.md` schema | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| F4 | `UNIVERSAL.md` — one schema for all agents | ⭐⭐⭐ | Ss1024sS | v0.2 |
| F5 | Adapter registry (`llmwiki.adapters.REGISTRY`) | ⭐⭐⭐⭐⭐ | **None** (bashiraziz has folders, not registry) | v0.1 |
| F6 | Schema version tracking per adapter | ⭐⭐⭐⭐ | **None** | v0.1 |
| F7 | Graceful degradation on unknown record types | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
