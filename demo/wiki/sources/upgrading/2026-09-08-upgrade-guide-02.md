---
title: "Upgrade guide (part 2/5: 2.0.0 — static site, pipeline, and MCP (from v1.5.0))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, version-2-migration, mcp-breaking-changes, static-site, vault-migrations, install-automation, candidate-review-cli]
date: 2026-09-08
source_file: 
project: upgrading
model: 
last_updated: 2026-09-08
---
## Summary

This source documents the **2.0.0** upgrade path from **v1.5.0**, centered on retiring `llmwiki serve` in favor of static `site/index.html` and CLI candidate review, expanding the default `llmwiki all` pipeline to **sync → synth → build → graph → lint**, and aligning MCP tools with the CLI (`wiki_search`, `wiki_lint` JSON). It lists required post-upgrade steps (`install-automation`, `configure-sources`, named `migrate` subcommands, Cursor re-sync, rebuild) and catalogs breaking removals (`wiki_entity_search`, `consolidate-topics`, `synth --allow-unclassified`, invalid `question`/`comparison` page kinds). A short **v1.5.0** addendum covers rebuilding for Analytics layout and optional `migrate tools-used` for `CallMcpTool` expansion in raw sessions.

## Key Claims

- Bare **`llmwiki all`** now runs **sync and synth** by default; schedulers that only wanted the old behavior need **`--no-synth`** (or **`--no-sync --no-synth`**) after re-running **`llmwiki install-automation`** (#156).
- **`llmwiki serve`**, **`POST /api/candidates`**, and **`/wiki-serve`** are removed; candidate decisions use **`llmwiki candidates apply`** and the static **`/candidates.html`** flow (#109).
- MCP clients must replace **`wiki_entity_search`** with **`wiki_search`** and treat **`wiki_lint`** output as **`llmwiki lint --json`**; top-level keys **`orphans`** / **`broken_links`** are gone—filter **`issues`** by **`rule`** (#102, #150).
- Bare **`llmwiki sync`** loads every **enabled, ingest-ready** adapter whose store exists; **Obsidian** and **ChatGPT export** stay **opt-in** via **`enabled: true`** (#182).
- **`filters.exclude_headless`** defaults **on** for coding-agent adapters; older Cursor CLI rows may need re-sync for correct **`is_headless`**, **`sessionId`**, and timestamps (#180).
- **`llmwiki consolidate-topics`** and CLI **`export`** / **`reindex`** are removed; catalog reconciliation happens on **sync**, **synth**, and candidate actions; **`build`** is the site/export path (#82, #147, #112).
- **`wiki/archive/`** is cold storage: discarded candidates stay **resolved** in harvest, so the first lint after upgrade may show **more** broken links (#140).
- **`llmwiki build`** can one-shot backfill missing **`synth.pipeline`** in state files (v1.4.0-shaped state) without API tokens; **`migrate tools-used`** safely skips rows when the origin agent session file is gone (#163, TTL ~30 days).

## Key Quotes

> "Stop using `llmwiki serve` — open `<vault>/site/index.html`. Candidate decisions on `/candidates.html` execute via `llmwiki candidates apply --vault <vault> --actions -`" — defines the static-site + CLI review model replacing the old server (#109).

> "Bare `llmwiki sync` loads every enabled ingest-ready adapter whose store exists; `enabled: false` is honoured" — documents the #182 adapter enablement model after upgrade.

> "When the origin store is gone (TTL / deleted sessions), rows are skipped safely — the migrator never invents MCP tool names." — constraint on **`migrate tools-used`** vs blind **`sync --force`**.

## Connections

- [[llmwiki]] (entity) — product version **2.0.0** upgrade surface (CLI, pipeline, lint, migrations).
  - fact: Default **`all`** pipeline is sync → synth → build → graph → lint with lint fail mode **`never`** unless overridden (#156).
- [[Static Site]] (concept) — **`serve`** removed; **`build`** refreshes vendored highlight.js/vis-network, topic pages, and provenance links; **`--local-root`** supports portable paths (#109, #127).
- [[MCP Server]] (concept) — breaking JSON shape for **`wiki_lint`**; **`wiki_entity_search`** removed in favor of **`wiki_search(term, kind=…, format=…)`** (#102, #150).
- [[Adapters]] (concept) — post-upgrade **`configure-sources`** for Cursor Agent CLI, OpenClaw, Codex, and other non-Claude stores; Cursor IDE Composer via **`cursor_ide`** after Enable (#182, #2, #192).
- [[Wiki Synthesis]] (concept) — **`synthesize`** removed; prefer **`llmwiki synth`** with **`--sources-only`** for legacy sources-only runs; promote can copy empty Key Facts from source **`fact:`** bullets without an LLM (#90, #112, #147).
- [[Cursor]] (entity) — **`cursor_cli`** vs **`cursor_ide`**; re-sync for headless metadata; optional **`migrate broken-provenance`** after bad **`source_file`** hops (#180).
- [[Wikilinks]] (concept) — **`provenance_integrity`** lint may surface broken **`sources:`** / **`source_file:`** chains (#122).
- [[Claude Code]] (entity) — **`llmwiki install-agent-kit --dest PATH`** replaces manual **`.claude/commands`** and **`.claude-plugin/`** copy (#109).
