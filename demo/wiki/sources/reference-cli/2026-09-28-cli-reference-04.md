---
title: "CLI reference (part 4/19: graph — build the knowledge graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, graphify, graph-visualization, wikilinks]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This CLI reference page documents the `graph` command in llmwiki, which builds knowledge graph visualizations from [[Wikilinks]]. The command supports two graph engines: a builtin stdlib-based engine for lightweight wikilink extraction, and an optional AI-powered Graphify engine that adds semantic analysis, community detection, and god-node identification.

## Key Claims

- The `graph` command generates knowledge graphs in JSON and/or HTML formats (default: both)
- The builtin engine produces an interactive vis-network visualization that is auto-copied to `site/` during build for offline static site access
- The Graphify engine performs tree-sitter AST extraction for code and semantic analysis for documentation, then applies Leiden community detection
- Graphify requires the optional dependency `pip install graphifyy` (or `pip install llm-wiki-plus[graph]`)
- Graph outputs from Graphify are written to `graphify-out/` then copied to `graph/` for build compatibility

## Key Quotes

> "The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch."

This design ensures the knowledge graph visualization is self-contained and performant within the static site, avoiding runtime CDN dependencies.

## Connections

- [[llmwiki]] (entity) — the project providing this CLI command
  - fact: `graph` is a core command for generating visual representations of the knowledge base
- [[Knowledge Graph]] (concept) — what the command constructs from wikilinks
  - fact: Supports both simple stdlib extraction and AI-enhanced semantic analysis via optional engines
- [[Wikilinks]] (concept) — the source material for graph construction
  - fact: Builtin engine extracts wikilinks using stdlib; Graphify adds semantic understanding and community detection
- [[Graphify]] (entity) — optional AI-powered graph analysis engine
  - fact: Provides tree-sitter AST extraction, semantic analysis, Leiden community detection, and god-node analysis; requires separate pip installation

## Contradictions

None identified.