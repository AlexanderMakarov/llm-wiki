---
title: "Upgrade guide (part 4/8: 2.1.0 — MCP tool consolidation (#196))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, mcp-consolidation, breaking-changes, cursor-ide-integration, static-site-serving]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This is part 4 of an 8-part upgrade guide for version 2.1.0, which consolidates the [[MCP Server]] (entity) to exactly six canonical tools and introduces breaking changes across CLI, [[Adapters]] (entity), synthesis, site generation, and automation. Key changes include replacing `llmwiki serve` with static HTML files, integrating [[Cursor]] (entity) IDE Composer as a first-class ingest adapter, making the default `llmwiki all` pipeline include sync → synth → build → graph → lint, and changing MCP tool aliases to hard removals. Migration steps are provided for users upgrading from v1.5.0.

## Key Claims

- The MCP server now registers exactly six tools with no alias stubs: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`; all retired tools (`wiki_query`, `wiki_list_sources`, `wiki_confidence`, `wiki_dashboard`, etc.) are removed entirely.
- `llmwiki all` now defaults to the complete pipeline (sync → synth → build → graph → lint); users upgrading existing automation must re-run `install-automation` or pass `--no-synth` / `--no-sync` to preserve old behaviour.
- [[Static Site]] (concept) serving replaces `llmwiki serve`; users open `<vault>/site/index.html` directly; highlight.js and vis-network are vendored into the site.
- Cursor IDE Composer ingest is newly integrated and works via bare `llmwiki sync` after running `configure-sources`; Cursor Agent CLI remains a separate adapter (`cursor_cli`).
- Adapter enable/disable flags are now honoured; Obsidian and ChatGPT export remain opt-in; `filters.exclude_headless` (default on) skips automated launches for coding-agent adapters.
- `synth --estimate` now follows synthesis state rather than pages-on-disk; migrations for `page-kinds` and `topic-kinds` are provided as cheaper catch-up than full re-synthesis.
- Lint JSON output shape changed to match CLI output; `--lint-fail never` is the new default for `all`; old keys like `orphans` and `broken_links` are removed.

## Key Quotes

> "The stdio MCP server registers **six** tools: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`. There are no alias stubs for retired names." — Tool consolidation is irreversible; clients using retired tools will fail immediately.

> "**`llmwiki all` default pipeline** is `sync` → `synth` → `build` → `graph` → `lint`" — A major orchestration shift that will change behaviour of existing cron jobs and automation unless reconfigured.

> "**Cursor IDE Composer ingest works via bare `llmwiki sync` after `configure-sources` Enable**" — Expansion of ingest surface; Cursor IDE is now first-class alongside Obsidian and ChatGPT.

> "**Stop using `llmwiki serve`** — open `<vault>/site/index.html`." — Dynamic serving is removed in favour of static files for security and simplicity.

## Connections

- [[llmwiki]] (entity) — Core system; all breaking changes apply to the project
  - fact: Default pipeline for `llmwiki all` is now sync → synth → build → graph → lint.
  - fact: Multiple CLI commands and flags are removed without deprecation stubs.

- [[MCP Server]] (entity) — Primary scope of v2.1.0 changes; tool surface consolidated to six
  - fact: Six canonical tools: wiki_search, wiki_read_page, wiki_health, wiki_sync, wiki_export, wiki_add.
  - fact: Retired tools include wiki_query, wiki_list_sources, wiki_confidence, wiki_dashboard, wiki_lint (replaced by wiki_health).

- [[Adapters]] (entity) — Adapter configuration and availability changed significantly
  - fact: Cursor IDE Composer adapter now integrated into bare sync workflow after configure-sources.
  - fact: enabled/disabled flags are now honoured; Obsidian and ChatGPT export remain opt-in.
  - fact: filters.exclude_headless (default on) skips automated launches for coding-agent adapters.

- [[Cursor]] (entity) — Cursor IDE now has first-class ingest integration
  - fact: Cursor IDE Composer works via llmwiki sync after configure-sources Enable.
  - fact: Cursor Agent CLI remains separate as cursor_cli adapter; IDE is cursor_ide.

- [[Obsidian]] (entity) — Adapter availability unchanged but now explicitly opt-in
  - fact: Obsidian adapter remains opt-in with adapters.obsidian.enabled: true.

- [[Wiki Synthesis]] (concept) — Synthesis logic and command defaults restructured
  - fact: synth --estimate follows synth state rather than pages-on-disk; state-based estimation replaces disk-based.
  - fact: Bare synth rewrites source pages lacking parseable topic bullets on next run; migrate topic-kinds provided as cheap catch-up.
  - fact: Promote no longer requires LLM for empty Key Facts; they copy from source `fact:` bullets.

- [[Static Site]] (concept) — Site generation replaces dynamic serving entirely
  - fact: llmwiki serve command removed; users open <vault>/site/index.html directly.
  - fact: highlight.js and vis-network are vendored; build refreshes site/ assets.
  - fact: candidates apply rebuilds site/ unless --no-rebuild is passed.

- [[GitHub Actions]] (entity) — Automation orchestration substantially changed
  - fact: install-automation is now a plain-language wizard with --schedule and --job {ingest,maintain}.
  - fact: Legacy --with-sync, --with-synth parse but are inert; use --no-sync, --no-synth instead.
  - fact: --profile {A,B,C} deprecated in favour of job-type selection.

## Contradictions

None noted. The document is internally consistent and supersedes v1.5.0 behaviour without documented contradiction to prior wiki content on earlier versions.