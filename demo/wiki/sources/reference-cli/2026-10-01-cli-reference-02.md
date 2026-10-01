---
title: "CLI reference (part 2/19: add — add a document to the wiki (#16 / #273))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cascade-delete, synthesis-control, ai-exports, vault-overlay]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This reference documents three core [[llmwiki]] CLI commands. `add` ingests URLs, files, folders, or stdin into raw Markdown without synthesizing wiki sources by default (synthesis requires explicit `--synthesize`). `remove` cascade-deletes raw docs and all derived artifacts (state keys, wiki pages, backlinks) to maintain referential integrity. `build` compiles wiki Markdown to static HTML and generates AI-consumable exports (graphs, feeds, LLM-friendly markdown). Key design: synthesis and site-building are decoupled operations, both opt-in to prevent unintended overhead.

## Key Claims

- The `add` command converts input sources into raw Markdown under `raw/docs/` and rebuilds the site by default, but does **not** synthesize `wiki/sources/` unless `--synthesize` is explicitly passed
- The `remove` command cascade-deletes raw docs along with every derived artifact (state keys, part-pages, backlinks), guaranteeing no orphan pages or dangling state remain
- Stdin sources receive frontmatter `source: "piped"` with no `/tmp/…` provenance path, establishing a source-layer guardrail
- URL sources flow through a layered pipeline: markdown negotiation → extraction → optional render escalation (headless browser)
- The `build` command generates seven AI-consumable exports (`llms.txt`, `graph.jsonld`, `rss.xml`, `sitemap.xml`, `robots.txt`, `ai-readme.md`) alongside HTML output
- Synthesis is off by default; the deprecated `--no-synthesize` flag remains as a no-op for backward compatibility

## Key Quotes

> "Does not synthesize `wiki/sources/` unless you pass `--synthesize`."
— Establishes that synthesis is opt-in, avoiding unintended processing overhead on every document addition.

> "Every artifact derived from them — the `synth.files` state keys and the `wiki/sources/` pages (part-pages included) — so a naive delete can never leave orphan pages or dangling state behind."
— Defines the cascade deletion guarantee that maintains referential integrity.

> "Stdin (`add -`) and MCP `content` use the piped-text conversion path: frontmatter `source: "piped"` (never a `/tmp/…` provenance)."
— Source-layer guardrail ensuring frontmatter accuracy for piped input.

## Connections

- [[llmwiki]] (entity) — Core system operated by these three commands; `add`, `remove`, and `build` are primary CLI interfaces
  - fact: Commands use `python3 -m llmwiki` invocation; `remove` appends to `wiki/log.md` after cascade deletion
  - fact: The `add` command supports MCP proxy via `wiki_add` (thin wrapper onto shared `run_add` path)
- [[Wiki Synthesis]] (concept) — Controlled by `--synthesize` flag on both `add` and `build`; disabled by default to preserve separation of concerns
  - fact: `build --synthesize --claude PATH` invokes overview synthesis via the Claude binary
  - fact: `add --synthesize` runs synthesis only on newly ingested docs with same rollback rules as standard synthesis
- [[Static Site]] (concept) — The `build` command compiles wiki Markdown into HTML and generates machine-readable metadata
  - fact: Default output directory is `./site/`; includes interactive graph viewer and 94 editorial pages in full example
  - fact: `--search-mode` flag controls routing: `auto` (default), `tree`, or `flat` based on heading depth
- [[Adapters]] (concept) — The `--vault PATH` flag enables vault-overlay mode for ingesting from external Obsidian / Logseq sources
  - fact: `add` and `build` both support `--vault PATH` to work with alternate vault directories
  - fact: `build --local-root PATH` substitutes home directories for portability across machines
- [[MCP Server]] (entity) — The MCP `wiki_add` is a thin proxy onto the shared CLI `run_add` path
  - fact: Provides model-context-protocol interface to the same document ingestion pipeline

## Contradictions

None identified. The document correctly reflects that synthesis is opt-in (closed by [[llmwiki]] design decision #273); the deprecated `--no-synthesize` flag remains as a compatibility shim.