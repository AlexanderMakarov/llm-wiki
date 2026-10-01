---
title: "CLI reference (part 4/19: graph — build the knowledge graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, knowledge-graph, graph-visualization, graphify, wikilink-extraction]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Documentation for the `graph` CLI command in llmwiki, which constructs a knowledge graph from wiki pages. Two engines are available: a builtin wikilink-extraction engine and an optional AI-powered graphify engine featuring semantic analysis and community detection. Output formats include JSON, HTML interactive visualization, or both, with automatic integration into the static site build.

## Key Claims

- The `graph` command extracts wikilink relationships to construct a knowledge graph of wiki structure
- Two engines are available: builtin (stdlib wikilink graph) and graphify (AI-powered with tree-sitter AST extraction, semantic analysis, Leiden community detection)
- The builtin engine outputs `graph/graph.json` and an interactive HTML viewer (`graph/graph.html`) using vis-network
- Graph files are automatically copied to `site/` during every build, enabling offline access without CDN dependencies
- The graphify engine requires `pip install llm-wiki-plus[graph]` or standalone `pip install graphifyy`
- Output format is configurable via `--format {json,html,both}` (default: both)

## Key Quotes

> "The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch." — Demonstrates tight integration of graph visualization with static site deployment.

> "Graphify engine: Runs the Graphify pipeline: tree-sitter AST extraction for code, semantic analysis for docs, Leiden community detection, god-node analysis." — Describes the AI-powered capabilities of the advanced graph engine.

## Connections

- [[Knowledge Graph]] (concept) — The graph command is the primary implementation for building and visualizing knowledge graphs in llmwiki
  - fact: The builtin engine extracts wikilink relationships from pages to construct the knowledge graph
  - fact: The graphify engine adds AI-powered semantic analysis and community detection to enhance graph structure
- [[Wikilinks]] (concept) — Wikilink parsing is the foundation of the builtin graph engine
  - fact: The builtin graph engine performs "stdlib wikilink graph" extraction
- [[llmwiki]] (entity) — The graph command is a core CLI feature for knowledge graph synthesis
  - fact: Graph output integrates automatically with the static site build process via `site/` directory copying

## Contradictions

None identified — this is reference documentation without comparison to prior work.