---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 3/5)"
slug: llmwiki-roadmap-phase-layer-item-prioritised-03
project: llmwiki-roadmap-phase-layer-item-prioritised
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/roadmap.md"
content_sha256: d84808a92adbc0c1aac2eb99e3b5bed4e5cee5f11a556cc320b99ac09ad8a6b1
---

> Part 3 of 5 of **llmwiki Roadmap — Phase × Layer × Item, prioritised**.

| Pri | Layer | ID | Item | Notes |
|:-:|:-:|:--|:--|:--|
| M | L0 | M-L0-01 | **Claude Code `.jsonl` adapter produces clean markdown** | Uses frontmatter, redacts PII, truncates tool output |
| M | L0 | M-L0-02 | **Redaction (username, API keys, tokens, emails)** on by default | Regex-based; patterns configurable |
| M | L0 | M-L0-03 | **Idempotent mtime state file** (`.llmwiki-state.json`) | Re-run is a sub-second no-op |
| M | L0 | M-L0-04 | **Live-session detection** — skip anything with last record `<60min` old | Prevents mid-write reads |
| M | L0 | M-L0-05 | **Sub-agent file handling** — render as separate page, link to parent | `is_subagent: true` in frontmatter |
| M | L0 | M-L0-06 | **`.llmwikiignore`** — skip listed files/projects | One pattern per line, gitignore syntax |
| M | L1 | M-L1-01 | `/wiki-ingest` workflow in CLAUDE.md + AGENTS.md | Karpathy 10-step flow |
| M | L1 | M-L1-02 | `/wiki-query` workflow with `[[wikilink]]` citations | |
| M | L1 | M-L1-03 | `/wiki-lint` workflow — orphans, broken links, contradictions, stale | |
| M | L1 | M-L1-04 | `/wiki-init` scaffold | Creates `raw/`, `wiki/`, seeds `index.md`, `log.md`, `overview.md` |
| M | L1 | M-L1-05 | Source page template with YAML frontmatter | `title`, `type: source`, `tags`, `date`, `source_file`, `project` |
| M | L1 | M-L1-06 | Entity page template (`TitleCase.md`) | `title`, `type: entity`, `sources`, `last_updated` |
| M | L1 | M-L1-07 | Concept page template (`TitleCase.md`) | Same as entity but `type: concept` |
| M | L1 | M-L1-08 | Synthesis page template (`kebab-case.md`) | For saved `/wiki-query` answers |
| M | L1 | M-L1-09 | `index.md` catalog format | Sections: Overview / Sources / Entities / Concepts / Syntheses |
| M | L1 | M-L1-10 | `log.md` append-only format | `## [YYYY-MM-DD] <op> \| <title>` grep-parseable |
| M | L1 | M-L1-11 | `overview.md` living synthesis | Updated on every ingest if warranted |
| M | L1 | M-L1-12 | Contradiction-tracking rule | Never silently overwrite, record both claims |
| M | L2 | M-L2-01 | **HTML builder with god-level CSS** (Inter + JetBrains Mono + purple accent) | Single `build.py` |
| M | L2 | M-L2-02 | Python-markdown with `fenced_code`, `tables`, `toc`, `sane_lists` | Plus normaliser for bad list indent |
| M | L2 | M-L2-03 | **highlight.js syntax highlighting** for all fenced code blocks | Client-side, loaded from CDN |
| M | L2 | M-L2-04 | Per-session HTML page with breadcrumbs | Home › project › session |
| M | L2 | M-L2-05 | Per-project HTML page with session cards | Main sessions + sub-agents collapsed |
| M | L2 | M-L2-06 | Projects index page | Card grid |
| M | L2 | M-L2-07 | Sessions index page with sticky header | Sortable table |
| M | L2 | M-L2-08 | Home page with overview (claude CLI synthesis optional) | `--synthesize` flag |
| M | L2 | M-L2-09 | Strip duplicate H1 from session bodies | Hero already shows title |
| M | L2 | M-L2-10 | Normalise 2-space-indented fenced code blocks | Converter emits them indented inside lists |
| M | L2 | M-L2-11 | Pre-built client-side search index (JSON) | For L3 search to consume |
| M | L3 | M-L3-01 | **Cmd+K command palette** (vanilla JS) | Keyboard-driven nav |
| M | L3 | M-L3-02 | **Global fuzzy search** over pre-built index | Substring + token match |
| M | L3 | M-L3-03 | **Keyboard shortcuts**: `/` focus search, `Esc` clear, `g h` home, `g p` projects, `g s` sessions, `j/k` next/prev on tables | |
| M | L3 | M-L3-04 | **Dark mode toggle** with `data-theme` attribute + localStorage + system default | |
| M | L3 | M-L3-05 | **Copy-as-markdown button** on session pages (hidden textarea source) | Clipboard API + execCommand fallback |
| M | L3 | M-L3-06 | **Copy-code button** on every `<pre>` (JS-wrapped) | On-hover visibility |
| M | L3 | M-L3-07 | **Collapsible tool-result sections** (`<details>`) over 500 chars | Click to expand |
| M | L3 | M-L3-08 | **Reading progress bar** (CSS scroll-linked) | Top of the page |
| M | L3 | M-L3-09 | **Filter bar** on sessions table (project dropdown, date range, model) | Client-side JS filter |
| M | L3 | M-L3-10 | **Download .md button** on every session page | Links to `sources/<path>.md` copy |
| M | L3 | M-L3-11 | **Toast notifications** on copy success | 1.5s fade |
| M | L3 | M-L3-12 | **Focus rings** (a11y) + `prefers-reduced-motion` | |
| M | L3 | M-L3-13 | Mobile responsive (320 / 768 / 1080 breakpoints) | |
| M | L3 | M-L3-14 | Print-friendly CSS | `@media print` |
| M | L3 | M-L3-15 | HTTP server (`python3 -m http.server` wrapper) bound to 127.0.0.1 | `llmwiki serve --port 8765` |
| M | L4 | M-L4-01 | **`setup.sh` / `setup.bat`** — install + first sync | Idempotent, tested |
| M | L4 | M-L4-02 | **`sync.sh` / `sync.bat`** — convert new sessions | Wrapper over `python3 -m llmwiki sync` |
| M | L4 | M-L4-03 | **`build.sh` / `build.bat`** — regenerate HTML | `python3 -m llmwiki build` |
| M | L4 | M-L4-04 | **`serve.sh` / `serve.bat`** — start server | `python3 -m llmwiki serve` |
| M | L4 | M-L4-05 | `upgrade.sh` / `upgrade.bat` — pull + re-run setup | |
| M | L4 | M-L4-06 | `python3 -m llmwiki` module entry (`__main__.py`) | |
| M | L4 | M-L4-07 | `llmwiki.cli.main()` argparse CLI with subcommands | `init`, `sync`, `build`, `serve`, `adapters`, `version` |
| M | L4 | M-L4-08 | `python3 -m llmwiki adapters` lists available adapters | Shows which are installed on this machine |
| M | L5 | M-L5-01 | `CLAUDE.md` schema with Ingest / Query / Lint workflows | Karpathy-compliant |
| M | L5 | M-L5-02 | `AGENTS.md` schema (mirror CLAUDE.md, agent-agnostic) | |
| M | L5 | M-L5-03 | **`.kiro/steering/` always-loaded rules** | contributing, page-format, verification |
| M | L5 | M-L5-04 | `docs/framework.md` — adapted open-source framework | With research phase + kiro style |
| M | L5 | M-L5-05 | `docs/architecture.md` — three-layer + 8-layer breakdown | |
| M | L5 | M-L5-06 | `docs/research.md` — Phase 1.25 research report | |
| M | L5 | M-L5-07 | `docs/feature-matrix.md` — all 161 features | |
| M | L5 | M-L5-08 | `docs/roadmap.md` — this document | |
| M | L5 | M-L5-09 | `docs/getting-started.md` — user install + first run | |
| M | L5 | M-L5-10 | `docs/configuration.md` — every config option | |
| M | L5 | M-L5-11 | `docs/adapters/claude-code.md` — Claude adapter usage | |
| M | L5 | M-L5-12 | `docs/adapters/codex-cli.md` — Codex adapter usage | |
| M | L5 | M-L5-13 | `docs/adapters/obsidian.md` — Obsidian adapter usage | |
| M | L5 | M-L5-14 | `docs/windows-setup.md` — Windows gotchas | |
| M | L5 | M-L5-15 | `docs/privacy.md` — redaction + local-only binding + no telemetry | |
| M | L5 | M-L5-16 | `README.md` with badges, pitch, demo link, install | |
| M | L5 | M-L5-17 | `CHANGELOG.md` per Keep-a-Changelog | |
| M | L5 | M-L5-18 | `LICENSE` (MIT) | |
| M | L6 | M-L6-01 | `llmwiki.adapters.base.BaseAdapter` | Interface + defaults |
| M | L6 | M-L6-02 | `llmwiki.adapters.claude_code.ClaudeCodeAdapter` | Production |
| M | L6 | M-L6-03 | `llmwiki
