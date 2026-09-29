---
title: "CLI reference (part 2/19: add — add a document to the wiki (#16 / #273))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, document-ingestion, cascade-deletion, static-generation]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

Reference documentation for three core [[llmwiki]] CLI commands: `add` (ingests documents from URLs, files, folders, or stdin into `raw/docs/` and rebuilds the site), `remove` (cascade-deletes raw docs and all derived artifacts to prevent orphans), and `build` (compiles wiki markdown to static HTML with AI-consumable exports).

## Key Claims

- The `add` command does NOT synthesize `wiki/sources/` unless the `--synthesize` flag is explicitly passed—synthesis is off by default
- The `remove` command cascade-deletes not just the raw document but also all `synth.files` state keys and derived `wiki/sources/` pages (including part-pages), preventing orphaned artifacts
- The `build` command writes seven AI-consumable exports: ai-readme.md, graph.jsonld, llms-full.txt, llms.txt, robots.txt, rss.xml, and sitemap.xml
- Stdin input (`add -`) sets frontmatter `source: "piped"` instead of deriving a temporary path
- The `remove` command requires `--yes` flag when stdin is not a TTY to prevent silent cascade deletion

## Key Quotes

> "Converts a URL, file, folder, or stdin in the process locale encoding (`-`) into raw Markdown under `raw/docs/`, then (by default) rebuilds the site so the new material is visible on Raw / Home. **Does not** synthesize `wiki/sources/` unless you pass `--synthesize`." — Establishes that synthesis is opt-in for `add`, not automatic.

> "so a naive delete can never leave orphan pages or dangling state behind" — The safety guarantee of cascade deletion: `remove` prevents orphaned derived artifacts.

> "Source-layer guardrail: pass the user's exact path, URL, or text. Do not reconstruct input from `wiki/sources/` or other derived pages unless the user asked." — The `add` command preserves original source identity to avoid circular references.

## Connections

- [[llmwiki]] (entity) — These CLI commands implement core workflows for document ingestion, artifact management, and site generation.
- [[Adapters]] (entity) — The `add` command converts multiple input formats (URLs, files, folders, stdin) to Markdown via a layered pipeline.
  - fact: The `add` command runs URLs through markdown negotiation → extraction → render escalation before landing as Markdown.
- [[Static Site]] (entity) — The `build` command compiles wiki markdown to HTML and exports AI-consumable formats.
  - fact: The `build` command outputs site/ HTML (703 files typical) plus seven AI-consumable exports (llms.txt, graph.jsonld, rss.xml, etc.).
- [[Wiki Synthesis]] (concept) — The `add` command's `--synthesize` flag controls whether `wiki/sources/` pages are generated for new raw documents.
  - fact: By default, `add` writes to `raw/docs/` without synthesis; `--synthesize` opts into the wiki sources pipeline.
- [[Knowledge Graph]] (concept) — The `build` command generates graph.jsonld and interactive site/graph.html for knowledge graph visualization.
  - fact: The `build` command produces graph.jsonld (JSON-LD structured data) and renders an interactive graph viewer.
- [[Obsidian]] (entity) — The `build` command's `--vault` flag enables vault-overlay mode to render existing Obsidian (and Logseq) vaults as static sites.
  - fact: The `build` command supports `--vault PATH` for building from existing note-taking vaults without requiring llmwiki's internal structure.