---
title: "llmwiki Roadmap — Phase × Layer × Item, prioritised (part 4/5)"
slug: llmwiki-roadmap-phase-layer-item-prioritised-04
project: llmwiki-roadmap-phase-layer-item-prioritised
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/roadmap.md"
content_sha256: d84808a92adbc0c1aac2eb99e3b5bed4e5cee5f11a556cc320b99ac09ad8a6b1
---

> Part 4 of 5 of **llmwiki Roadmap — Phase × Layer × Item, prioritised**.

.adapters.codex_cli.CodexCliAdapter` | v0.1 **stub** |
| M | L6 | M-L6-04 | **`llmwiki.adapters.obsidian.ObsidianAdapter`** | Reads `~/Documents/Obsidian Vault/` |
| M | L6 | M-L6-05 | Adapter auto-discovery | `REGISTRY` populated on import |
| M | L6 | M-L6-06 | `SUPPORTED_SCHEMA_VERSIONS` constant per adapter | Schema-version rule |
| M | L6 | M-L6-07 | Graceful degradation on unknown record types | Log DEBUG, never crash |
| M | L7 | M-L7-01 | `.github/workflows/ci.yml` — lint + build smoke on push/PR | |
| M | L7 | M-L7-02 | `.github/workflows/gitleaks.yml` — secret scan | |
| M | L7 | M-L7-03 | `.github/workflows/pages.yml` — GitHub Pages on tag push | |
| M | L7 | M-L7-04 | `tests/fixtures/claude_code/*.jsonl` — synthetic fixtures | |
| M | L7 | M-L7-05 | `tests/test_claude_adapter.py` — snapshot tests | |
| M | L7 | M-L7-06 | `tests/test_convert.py` — converter unit tests | |
| M | L7 | M-L7-07 | `tests/test_build.py` — HTML build smoke | |
| M | L7 | M-L7-08 | Privacy grep in CI (`grep -r '<real_username>' site/` → fail on hit) | |
| M | L7 | M-L7-09 | Performance budget check — build time `<15s`, HTML `<50MB` | |
| M | L7 | M-L7-10 | `CONTRIBUTING.md` + PR template + issue templates | |
| S | L0 | S-L0-01 | Obsidian adapter reads `.md` files directly (no conversion) | Skip `.obsidian/`, trash, templates |
| S | L0 | S-L0-02 | Cursor adapter | |
| S | L0 | S-L0-03 | PDF ingestion (pypdf) | |
| S | L1 | S-L1-01 | `/wiki-update` — update existing page only | |
| S | L1 | S-L1-02 | `/wiki-graph` — networkx + vis.js knowledge graph | |
| S | L1 | S-L1-03 | `/wiki-reflect` — self-reflection across all wiki | |
| S | L1 | S-L1-04 | `/wiki-archive` — move stale entries to `wiki/archive/` | |
| S | L1 | S-L1-05 | ~~Comparison page type~~ | Declined 2026-08-09 (#109) — no producer, no perceived value |
| S | L1 | S-L1-06 | ~~Question page type~~ | Declined 2026-08-09 (#109) — no producer, no perceived value |
| S | L2 | S-L2-01 | Timeline view of sessions | |
| S | L2 | S-L2-02 | Tag cloud / tag index page | |
| S | L2 | S-L2-03 | Knowledge graph HTML (vis.js) | |
| S | L2 | S-L2-04 | Backlinks section at the bottom of every page | |
| S | L3 | S-L3-01 | Hover-to-preview wikilinks | |
| S | L3 | S-L3-02 | Session timeline chart (sparkline) | |
| S | L3 | S-L3-03 | Search result snippets with highlights | |
| S | L3 | S-L3-04 | Scroll-spy for breadcrumbs | |
| M | L4 | M-L4-09 | **Claude Code plugin packaging** (`.claude-plugin/plugin.json` + `marketplace.json`) | Promoted from S → M on 2026-04-08 |
| M | L4 | M-L4-10 | `.claude/commands/wiki-sync.md`, `wiki-ingest.md`, `wiki-query.md`, `wiki-lint.md`, `wiki-build.md`, `wiki-serve.md` | 6 slash commands |
| M | L4 | M-L4-11 | `.claude/skills/llmwiki-sync/SKILL.md` + `llmwiki-ingest/SKILL.md` + `llmwiki-query/SKILL.md` | Auto-discoverable skills |
| M | L4 | M-L4-12 | **MCP server** exposing `wiki_query`, `wiki_ingest`, `wiki_search`, `wiki_lint` tools | Promoted from S → M on 2026-04-08. Stub in v0.1, full in v0.2. |
| M | L4 | M-L4-13 | `.claude/launch.json` for Claude_Preview integration | Lets contributors preview llmwiki from inside Claude Code |
| S | L4 | S-L4-01 | Claude Code plugin packaging (`.claude-plugin/plugin.json`) | marketplace-ready |
| S | L4 | S-L4-02 | `pip install llm-notebook` on PyPI | |
| S | L4 | S-L4-03 | Homebrew formula | |
| S | L5 | S-L5-01 | Domain examples (personal / research / business) | |
| S | L5 | S-L5-02 | Use-case examples (solo / team / multi-agent) | |
| S | L5 | S-L5-03 | MCP server doc | |
| S | L5 | S-L5-04 | Knowledge-system playbook | |
| S | L6 | S-L6-01 | Codex CLI full implementation (from stub) | |
| S | L6 | S-L6-02 | Gemini CLI adapter | |
| S | L6 | S-L6-03 | Cursor adapter | |
| S | L6 | S-L6-04 | OpenCode / OpenClaw adapter | |
| S | L7 | S-L7-01 | Release automation (tag-push → GitHub Release) | |
| S | L7 | S-L7-02 | Dependabot for GitHub Actions | |
| S | L7 | S-L7-03 | Link checker in CI | |
| C | L1 | C-L1-01 | `/wiki-merge` — merge two vaults | |
| C | L1 | C-L1-02 | `/wiki-compile` — multi-step pipeline | |
| C | L2 | C-L2-01 | Inline diff view for `/wiki-update` changes | |
| C | L3 | C-L3-01 | Page transitions / subtle animations | |
| C | L4 | C-L4-01 | Docker image | |
| C | L5 | C-L5-01 | i18n for docs (zh-CN, ja, es) | |
| C | L6 | C-L6-01 | Web clipper / URL ingestion | |
| C | L6 | C-L6-02 | Image ingestion (OCR) | |
| C | L6 | C-L6-03 | Local LLM via Ollama | |
| C | L7 | C-L7-01 | Eval framework (LLM-judged wiki quality) | |
| C | L7 | C-L7-02 | SQLite FTS5 server-side search fallback | |
| W | L0 | W-L0-01 | Slack / Discord export ingestion | Out of scope |
| W | L2 | W-L2-01 | TUI browser | Defer to raine/claude-history |
| W | L3 | W-L3-01 | Real-time collaborative editing | Not a product goal |
| W | L4 | W-L4-01 | Precompiled Go/Rust binary | Python-first policy |
| W | L7 | W-L7-01 | Sentry / telemetry | Privacy rule |
| W | L7 | W-L7-02 | Supabase / Postgres backend | Stdlib-first rule |
