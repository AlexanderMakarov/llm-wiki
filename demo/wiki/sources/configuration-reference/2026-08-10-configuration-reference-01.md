---
title: "Configuration Reference (part 1/4)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, session-sync, ai-exports, static-site-build, full-pipeline]
date: 2026-08-10
source_file: 
project: configuration-reference
model: 
last_updated: 2026-08-11
---
## Summary

Part 1 of a comprehensive CLI reference documenting the `llmwiki` tool's 8 subcommands and their flags. Covers project initialization, session transcript ingestion/conversion, HTML compilation with AI-consumable exports, local serving, adapter registry, knowledge graph generation, full-pipeline orchestration, and version querying.

## Key Claims

- `sync` converts `.jsonl` session transcripts into markdown under `raw/sessions/`, with filters for adapter, date range, and project name
- `build` generates both static HTML and AI-consumable exports: `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, and `ai-readme.md`
- The `--force-resync` flag bypasses schema/state guards (per issue #29) and may duplicate sessions if `raw/` is already populated
- `build --synthesize` calls the `claude` CLI to auto-generate an Overview summary
- The `all` command (v1.2) orchestrates the complete pipeline with optional sync/synthesis and fine-grained skip/force flags

## Key Quotes

> "Convert agent session transcripts (`.jsonl`) into markdown under `raw/sessions/`." — core function of `sync`

> "writes AI-consumable exports into the output directory: `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, and `ai-readme.md`" — primary outputs of `build`

> "Run the full pipeline: `[sync?]` → `[synthesize?]` → build → graph → lint." — scope of the `all` command

## Connections

None yet (part 1 of 4; subsequent parts and peer documentation will establish cross-references).

## Contradictions

None evident. (This is a reference document; contradictions with actual behavior should be noted when discovered.)