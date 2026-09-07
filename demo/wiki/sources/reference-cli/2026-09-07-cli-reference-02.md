---
title: "CLI reference (part 2/15: remove — cascade-remove a raw doc and everything derived (#B2))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cascade-deletion, static-site-generation, build-configuration]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-02.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This session documents two core [[llmwiki]] CLI subcommands: `remove` performs cascade deletion of raw docs and all derived artifacts (state keys and wiki/sources/ pages), then prunes backlinks and updates the log; `build` compiles wiki markdown to static HTML and generates AI-consumable exports (llms.txt, sitemap.xml, rss.xml, graph.jsonld, etc.) with configurable search modes and [[Obsidian]]/[[Logseq]] vault overlay support.

## Key Claims

- The `remove` command cascade-deletes raw docs and all derived artifacts (synth.files state keys and wiki/sources/ pages) in a single atomic operation
- After removal, `remove` prunes backlinks, rebuilds wiki/index.md, and appends a `remove` entry to wiki/log.md
- A selector that matches nothing results in a clean no-op with a message
- There is no separate `export` subcommand; AI-consumable exports are generated as part of the `build` command
- The `--local-root` flag substitutes stored home directories with a fixed value to enable reproducible rendering of the same vault across different machines
- The `--vault` flag enables overlay mode for building from existing [[Obsidian]] or [[Logseq]] vaults
- The `--search-mode` flag supports three options: `auto` (picks tree vs flat based on heading depth), `tree`, and `flat`, defaulting to `auto`

## Key Quotes

> "cascade-remove a raw doc and everything derived from them — the `synth.files` state keys and the `wiki/sources/` pages"
> — defines the full scope of cascade deletion

> "cascade deletion is never silent"
> — design principle: deletion requires explicit confirmation via `--yes` on non-TTY environments or interactive prompt on TTY

> "there is no separate `export` subcommand"
> — exports are integrated into `build`, not a standalone operation

> "Pass a fixed string when publishing so the same vault renders identically anywhere"
> — `--local-root` enables reproducible builds across environments by substituting home directory references

## Connections

- [[llmwiki]] (project/tool) — the CLI application being documented
  - fact: Provides `remove` and `build` subcommands for managing wiki artifacts and generating static output
- [[Static Site]] (concept) — the `build` command generates HTML output
  - fact: Turns wiki/ markdown into site/ HTML and produces AI-consumable exports
- [[Obsidian]] (tool) — supported vault format for overlay mode
  - fact: `--vault` flag accepts Obsidian vault paths for building from existing vaults
- [[Logseq]] (tool) — supported vault format for overlay mode
  - fact: `--vault` flag accepts Logseq vault paths for building from existing vaults