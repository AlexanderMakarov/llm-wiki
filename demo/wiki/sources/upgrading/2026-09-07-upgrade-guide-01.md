---
title: "Upgrade guide (part 1/5)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, upgrade-guide, cli-reorganization, sync-lookback, mcp-consolidation]
date: 2026-09-07
source_file: raw/docs/upgrading/upgrade-guide-01.md
project: upgrading
model: 
last_updated: 2026-09-07
---
## Summary

Documents the upgrade path between `llmwiki` versions 2.2.0 and 2.1.0, covering major breaking changes: the PyPI package renamed to `llm-wiki-plus`, CLI commands reorganized into six lifecycle sections with `synthesize` → `synth` and migrations unified under `llmwiki migrate`, introduction of optional durable sync lookback via `filters.since` configuration, Cursor IDE adapter renamed to `cursor_ide`, and MCP tools consolidated from many deprecated aliases to six canonical tools.

## Key Claims

- The v2.2.0 distribution on PyPI is published as `llm-wiki-plus`, while the CLI binary and Python import remain `llmwiki` (#210)
- In v2.1.0, `llmwiki --help` was reorganized into six lifecycle sections; `synthesize` was renamed to `synth` with changed default behavior (sources-only → sources+harvest); all migration commands consolidated under `llmwiki migrate` (#112)
- Optional durable sync lookback via `filters.since` (shared) and `adapters.<name>.since` (per-source) gates ingestion by date and prunes older synced files on the next successful sync without deleting raw data (#192)
- The Cursor IDE adapter was renamed from `cursor` to `cursor_ide` to distinguish it from `cursor_cli`, with legacy `adapters.cursor` blocks still working but `cursor_ide` preferred in new configs
- MCP tools were consolidated to six canonical tools (`wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`), with no aliases for retired tools like `wiki_query`, `wiki_confidence`, or `wiki_lint` (#196)

## Key Quotes

> "Most releases are drop-in (`pip install -U llm-wiki-plus` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`."

> "Set a lookback before enabling a long-retention store so the first bare sync does not convert years of history."

> "The stdio MCP server registers **six** tools: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`. There are no alias stubs for retired names."

## Connections

- [[llmwiki]] (project) — the CLI tool and system being upgraded
  - fact: v2.2.0 distributed on PyPI as `llm-wiki-plus` with same CLI/import names
  - fact: v2.1.0 introduced three major features: CLI reorganization, durable sync lookback, MCP tool consolidation
- [[Configuration]] (concept) — sync lookback feature introduces optional date-gating for ingestion
  - fact: `filters.since` (shared) and `adapters.<name>.since` (per-adapter) control lookback window
  - fact: `llmwiki configure-sources` CLI provides interactive setup with default lookback of 30 days
- [[Configuration Reference]] (reference) — referenced for complete details on sync lookback configuration keys
- [[Cursor]] (product) — Cursor IDE adapter renamed from `cursor` to `cursor_ide` to disambiguate from `cursor_cli`

## Contradictions

None identified.