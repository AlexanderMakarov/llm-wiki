---
title: "Slash commands reference (part 3/4: /wiki-reflect)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, knowledge-graph, wiki-reflection, static-site-generation, pipeline-orchestration]
date: 2026-09-28
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-28
---
## Summary

Documents four slash commands for [[llmwiki]] pipeline orchestration: `/wiki-graph` builds the knowledge graph as JSON and HTML; `/wiki-reflect` performs higher-order self-analysis over the entire wiki (model-orchestrated, most token-intensive); `/wiki-build` regenerates the static HTML site; and `/wiki-all` runs the complete end-to-end pipeline (sync → synth → build → graph → lint) with optional flags to skip stages or adjust backends.

## Key Claims

- `/wiki-graph` wraps `python3 -m llmwiki graph` and emits `graph/graph.json` and `graph/graph.html` representing wiki pages as nodes and [[wikilinks]] as edges
- `/wiki-reflect` is a model-orchestrated workflow (no direct CLI wrapper) that analyzes the index, overview, and sample pages to identify gaps, patterns, and synthesis opportunities
- `/wiki-reflect` is the most token-intensive command and should be used sparingly
- `/wiki-all` orchestrates the full pipeline with optional flags: `--strict` converts lint warnings to non-zero exit codes for CI; `--no-synth` skips synthesis to avoid AI provider costs; `--skip-graph` or `--graph-engine builtin` bypass optional Graphify backend
- `graph.html` is automatically copied to `site/` during the build stage

## Key Quotes

> "Use sparingly; it's the most token-heavy command." — Guidance on `/wiki-reflect` resource consumption

> "run the full pipeline end-to-end — sync → synth → build → graph → lint" — How `/wiki-all` orchestrates the complete workflow

> "Pass `--strict` to turn any lint warning into a non-zero exit, which is exactly what CI wants." — CI/CD integration pattern

## Connections

- [[llmwiki]] (entity) — These are the primary operational slash commands for the system
  - fact: `/wiki-graph`, `/wiki-build`, `/wiki-all` wrap Python CLI subcommands; `/wiki-reflect` is model-orchestrated
  
- [[Knowledge Graph]] (concept) — `/wiki-graph` generates the graph structure
  - fact: Nodes represent wiki pages; edges are `[[wikilinks]]`
  - fact: Outputs both JSON and HTML formats
  
- [[Static Site]] (entity) — `/wiki-build` and `/wiki-all` produce the final website
  - fact: Regenerates HTML after manual edits or as part of full pipeline
  - fact: Graph visualization is copied to site during build
  
- [[Wiki Synthesis]] (concept) — `/wiki-reflect` and `/wiki-all --synth` perform analysis and synthesis
  - fact: `/wiki-reflect` reads samples to suggest improvements
  - fact: `--no-synth` flag allows cost-free CI runs
  
- [[GitHub Actions]] (entity) — `/wiki-all --strict` designed for CI/CD pipelines
  - fact: `--strict` converts warnings to exit codes for CI enforcement