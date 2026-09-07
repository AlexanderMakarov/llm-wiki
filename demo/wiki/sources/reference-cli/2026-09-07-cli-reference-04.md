---
title: "CLI reference (part 4/15: graph — build the knowledge graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, knowledge-graph, wiki-linting, cli-reference, quality-rules]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-04.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary
This CLI reference documents two core llmwiki commands: `graph` (for building and visualizing knowledge graphs) and `lint` (for structural wiki quality validation). The graph command supports both a lightweight builtin wikilink engine and an AI-powered Graphify engine with community detection. The lint command enforces 17 deterministic structural rules—including contradiction detection, link integrity checking, and orphan identification—with fine-grained control over which rules run and how failures are reported; three rules that previously required explicit opt-in now always run as of issue #72.

## Key Claims
- The `graph` builtin engine creates an interactive JSON/HTML viewer that auto-integrates into the static site for offline access without CDN dependency
- Graphify engine applies tree-sitter AST parsing, semantic analysis, and Leiden community detection to build AI-powered graphs
- The `lint` command runs 17 fully deterministic structural rules requiring no LLM
- As of issue #72, contradiction detection, claim verification, and summary accuracy rules no longer require `--include-llm` and instead run as structural checks on frontmatter and section structure
- Orphan detection recognizes both `[[wikilinks]]` and catalog markdown links (resolved case/punctuation-insensitively) as valid inbound references
- Lint rules can be disabled per-vault via `llmwiki.json` with recorded skip reasons

## Key Quotes
> "The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch." — demonstrates tight integration between graph visualization and static site generation

> "As of #72 they always run as structural checks: non-filler `## Contradictions` sections, entity/concept claims without sources, and empty `summary:` frontmatter." — marks a behavioral change making three validation rules always-on

## Connections
- [[Knowledge Graph]] (concept) — the `graph` command implements graph building and visualization
  - fact: Builtin engine uses stdlib wikilinks; Graphify engine uses tree-sitter, semantic analysis, and Leiden community detection
- [[llmwiki]] (entity) — the main project these CLI commands belong to
  - fact: `graph` and `lint` are core subcommands for knowledge graph construction and wiki quality assurance
- [[Configuration Reference]] (concept) — vault configuration controls lint rule behavior
  - fact: Lint rules can be disabled via committed `<vault>/llmwiki.json` with skip reasons

## Contradictions
None identified.