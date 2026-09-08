---
title: "Upgrade guide (part 1/5)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, version-upgrades, pypi-distribution, sync-lookback, mcp-server, synthesis-backend, llm-wiki-plus, cli-migration]
date: 2026-09-08
source_file: 
project: upgrading
model: 
last_updated: 2026-09-08
---
## Summary

Part 1 of the upgrade guide documents breaking or behaviour-changing steps between `llmwiki` releases: unreleased Home pipeline state and a slimmer Automation panel (#234), optional `cursor_cli` as a synthesis backend (#230), PyPI install as `llm-wiki-plus` (#210), 2.1.0 CLI lifecycle grouping and command renames (#112), durable sync lookback with `filters.since` and `cursor_ide` vs `cursor_cli` (#192), and MCP consolidation to six tools (#196). The guide complements CHANGELOG.md by focusing on what might break on the next `sync`, `synth`, or `build`.

## Key Claims

- The published PyPI package is **`llm-wiki-plus`**; import and CLI remain `llmwiki` (`pip install -U llm-wiki-plus`).
- **`synth`** replaces `synthesize` and by default runs sources plus harvest; **`synth --sources-only`** is the old sources-only path; **`consolidate-topics`** is removed (topic prep runs at the start of each sources pass).
- Vault migrations are subcommands of **`llmwiki migrate <name>`** (e.g. `migrate state`, `migrate raw-redaction`); list with `llmwiki migrate` or `--list`; nothing runs until a name is chosen.
- Optional **`filters.since`** and **`adapters.<name>.since`** limit first sync depth; a successful sync with durable lookback can GC older **`sync.files`** stamps for coding-agent adapters (not `raw/`); CLI **`--since`** overrides one run but does not GC.
- The contrib registry name for Cursor IDE is **`cursor_ide`** (not `cursor`); **`cursor_cli`** is the Agent CLI chat adapter; legacy `cursor` / `adapters.cursor` still work; `cursor::` sync keys rewrite to `cursor_ide::` on state load.
- **`synthesis.backend`** may be **`cursor_cli`** (shells to `agent` / `cursor-agent`); one-run override **`llmwiki synth --backend cursor_cli`** does not write `config.json`; ingest adapters are separate from the synthesis generator.
- Standalone **`llmwiki lint`** updates **`llmwiki-state.json`** and copies **`site/llmwiki-state.js`** without rewriting HTML; **`--lint-fail`** on **`all`** does not undo an earlier build in the same run.
- The stdio **MCP** surface is six tools: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`; retired tools map to `wiki_search` / `wiki_health` (no alias stubs).

## Key Quotes

> "Most releases are drop-in (`pip install -U llm-wiki-plus` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`." — scope of the upgrade guide vs CHANGELOG

> "**Not session ingest:** this is the synthesis *generator*. The contrib adapters `cursor_cli` (Agent CLI chats) and `cursor_ide` (IDE Composer) only convert transcripts into `raw/`." — separates synthesis backend from adapter ingest

> "**Set a lookback before enabling a long-retention store** so the first bare sync does not convert years of history." — operational warning for #192 lookback

## Connections

- [[llmwiki]] (entity) — release upgrade path, CLI renames, pipeline/lint state behaviour, and agent-kit pruning after upgrade (#214).
  - fact: Re-run `llmwiki install-agent-kit` after upgrade to drop retired slash commands such as `/wiki-export-marp` and `/wiki-synthesize`.
- [[MCP Server]] (entity) — six-tool consolidation (#196) and migration table from retired MCP names.
  - fact: `wiki_lint` → `wiki_health`; query/list/confidence-style tools → `wiki_search` with `question`, `list_sources`, or `mode=filter`.
- [[Cursor]] (entity) — `cursor_cli` synthesis backend (#230) and `cursor_ide` vs `cursor_cli` adapter naming (#192).
  - fact: Synthesis uses `composer-2.5` default and 180s timeout under `synthesis.cursor_cli`; ingest uses contrib adapters only for `raw/`.
- [[Adapters]] (concept) — sync lookback, enable column semantics, and `cursor_ide` registry rename with `sync.files` key rewrite.
  - fact: `llmwiki adapters` “enabled” is yes/no for whether the next bare `sync` includes the source; `active` / `auto` / `explicit` / `off` labels are gone.
- [[Wiki Synthesis]] (concept) — `synth` default (sources + harvest), `--sources-only`, and `build --synthesize` following the active backend.
  - fact: `build --synthesize` skips overview LLM when backend is `dummy` or unavailable.
- [[Static Site]] (concept) — Home pipeline Timeline vs Eligible/Knowledge tables (#234); lint-error note under Candidates; Automation panel is settings-only without stage timestamps.
  - fact: Site is described as refreshing once after summarization in maintain wording.
