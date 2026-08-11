---
title: "Architecture (part 2/3: Layer 2: The eight-layer build)"
slug: architecture-02
project: architecture
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/architecture.md"
content_sha256: f9d60b3a6d2545eb672aff3ec89271d5d5daf460c4cf2aa42001fe5d6fdfe471
---

> Part 2 of 3 of **Architecture** — Layer 2: The eight-layer build.

## Layer 2: The eight-layer build

Internally the code is organised into eight functional layers. Each layer has one clear responsibility, and each feature in [docs/roadmap.md](roadmap.md) maps to exactly one layer.

```
┌──────────────────────────────────────────────────────┐
│  L7  CI / ops          .github/workflows/            │
│  L6  Adapters          llmwiki/adapters/             │
│  L5  Schema / docs     CLAUDE.md, AGENTS.md, docs/   │
│  L4  Distribution      setup.sh, .bat, .claude/      │
│  L3  Viewer            script.js in build.py         │
│  L2  Site              build.py (HTML + CSS)         │
│  L1  Wiki              CLAUDE.md workflows           │
│  L0  Raw               llmwiki/convert.py            │
└──────────────────────────────────────────────────────┘
```

### L0 — Raw

Owner: `llmwiki/convert.py`

Reads .jsonl from the agent's session store (via an adapter), filters out noise records, runs redaction, normalises the output into markdown, and writes to `raw/sessions/`.

Key properties:

- **Idempotent** — mtime tracked in `<vault>/llmwiki-state.json` (unified queue + sync + synth + quarantine state)
- **Privacy-first** — username + API keys + tokens + emails redacted by default
- **Live-session safe** — skips files with a record younger than 60 minutes
- **Agent-agnostic** — delegates discovery to the adapter registry

**Vault state (v1.4+):** one active `llmwiki-state.json` per process, configured at the CLI border (`apply_default_vault` → `configure_state_file`). Library modules call `resolve_state_file()` — they never re-read `config.json` for the state path. Import-time constants like `DEFAULT_STATE_FILE` were removed so tests and library callers cannot accidentally write into a developer's configured vault.

### L1 — Wiki

Owner: your coding agent, following [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md)

llmwiki does NOT write to `wiki/` directly. The agent does, via slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) that execute the workflows in the schema file.

### L2 — Site (HTML generator)

Owner: `llmwiki/build.py`

Converts every file under `raw/sessions/` (and any hand-authored files under `wiki/`) into static HTML. Uses `python-markdown` (the only runtime dep) — syntax highlighting runs in the browser via highlight.js loaded from a pinned jsdelivr CDN (v0.5, #73), so the build pipeline itself stays stdlib-only. Writes to `site/`.

Pages rendered (v0.9 surface):

- `site/index.html` — home with hero + 365-day activity heatmap + token-usage stat grid + recently-updated card + project grid with topic chips
- `site/projects/index.html` — project grid with freshness badges
- `site/projects/<project>.html` — per-project page with topics strip, 365-day heatmap (scoped), tool-calling bar chart, token timeline, main sessions + sub-agents
- `site/sessions/index.html` — sortable sessions table with filter bar
- `site/sessions/<project>/<slug>.html` — per-session transcript with tool chart + token card + full conversation
- `site/models/index.html` — sortable AI-model directory (v0.7, #55)
- `site/models/<slug>.html` — per-model info card + changelog timeline + pricing sparkline (v0.7, #56)
- `site/vs/index.html` — auto-generated vs-comparison index (v0.7, #58)
- `site/vs/<a>-vs-<b>.html` — side-by-side info table + benchmark chart + price delta
- `site/index.html` — pipeline State dashboard (recent raw docs)
- `site/raw.html` — raw-docs file-tree browser (tree loaded from `documents-tree.js`)
- `site/documents/<path>.html` — one page per raw document file; shared tree sidebar loaded once via JS
- `site/documents-tree.json` (+ `.js` sidecar) — single shared doctree payload for Raw + document pages
- `site/recent.html` — newest raw documents, one row per logical document
- `site/analytics.html` — activity heatmap, token stats, project grid
- `site/search-index.json` — pre-built client-side search index
- `site/sources/<project>/<slug>.md` — copies of raw session markdown for download / agents
- Plus AI-consumable exports: `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`

Documents enter `raw/docs/` either via the asynchronous producer queue path or synchronously via `llmwiki add` (`llmwiki/add_doc.py`, #16) — both produce the same dir-per-doc, section-chunked layout.

### L3 — Viewer (browser JS)

Owner: `script.js` (a string constant inside `build.py`)

Everything that happens in the browser, in vanilla JS:

- Theme toggle with `data-theme` attribute + localStorage + system preference
- Reading progress bar (scroll-linked CSS)
- Copy-as-markdown + copy-code buttons (Clipboard API + `document.execCommand` fallback for HTTP)
- Auto-collapse of long tool-result sections into `<details>`
- Cmd+K command palette (fuzzy search over `search-index.json`)
- Keyboard shortcuts: `/`, `g h`, `g p`, `g s`, `j`, `k`, `?`
- Sessions-table filter bar (project, model, date range, slug text)

Zero dependencies. No bundler. No framework. One file.

### L4 — Distribution

Owner: the repo root + `.claude-plugin/`

How users install and run llmwiki:

- `setup.sh` / `setup.bat` — one-click install
- `sync.sh` / `sync.bat` — wrappers around `python3 -m llmwiki sync`
- `build.sh` / `build.bat` — wrappers around `python3 -m llmwiki build`
- `serve.sh` / `serve.bat` — wrappers around `python3 -m llmwiki serve`
- `upgrade.sh` / `upgrade.bat` — `git pull` + re-run setup
- `.claude-plugin/plugin.json` + `marketplace.json` — Claude Code plugin packaging
- `.claude/commands/` — 7 slash commands
- `.claude/skills/` — 5 auto-discoverable skills
- `llmwiki/mcp/` — MCP server stub

### L5 — Schema / docs

Owner: root-level markdown + `docs/`

Tells humans and agents how the system works:

- `CLAUDE.md` — Claude Code schema with Ingest / Query / Lint workflows
- `AGENTS.md` — Codex / OpenCode / Gemini mirror of the same
- `.kiro/steering/` — always-loaded contribution / format / verification rules
- `docs/framework.md` — Open Source Framework v4.1 adapted for llmwiki
- `docs/research.md` — Phase 1.25 research report
- `docs/feature-matrix.md` — 161 features across 16 categories
- `docs/roadmap.md` — Phase × Layer × Item MoSCoW table

### L6 — Adapters

Owner: `llmwiki/adapters/`

One file per agent. Each subclass of `BaseAdapter` does three things:

1. Knows where the agent writes its session store
2. Walks that store to discover `.jsonl` files
3. Derives a friendly project slug from the path

Everything else (record parsing, filtering, redaction, rendering) is shared in `convert.py`.

### L7 — CI / ops

Owner: `.github/workflows/` + `tests/`

- `ci.yml` — lint + tests + build smoke on every push + PR (Python 3.12 only)
- `gitleaks.yml` — secret scan
- `pages.yml` — build + deploy to GitHub Pages on tag push (Phase 6.5 Self-Demo)
- `tests/fixtures/<agent>/` — synthetic fixtures
- `tests/snapshots/<agent>/` — expected markdown outputs
- `tests/test_*.py` — pytest unit + snapshot tests
