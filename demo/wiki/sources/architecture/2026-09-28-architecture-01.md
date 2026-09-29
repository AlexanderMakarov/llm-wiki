---
title: "Architecture (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, architecture, layered-design, knowledge-graph-synthesis, wiki-maintenance, ingest-workflow]
date: 2026-09-28
source_file: 
project: architecture
model: 
last_updated: 2026-09-28
---
## Summary

This architectural document establishes llmwiki's two-layer conceptual model: Karpathy's three-layer wiki (raw → wiki → site) and an eight-layer implementation model. It defines how the immutable raw/ layer feeds synthesized wiki/ pages, which are filtered into candidates requiring human-or-agent review before promotion to trusted entities and concepts, finally rendering to a static site. The wiki/ layer is entirely LLM-maintained via the Ingest Workflow and compounds over time.

## Key Claims

- llmwiki architecture has two overlapping structures: a conceptual three-layer wiki (Karpathy's model) and an eight-layer implementation model distributing responsibilities across Python modules, templates, scripts, and CI.
- The raw/ layer is immutable source-of-truth; converters write one markdown file per session with YAML frontmatter, and no other process should modify this layer.
- The wiki/ layer is entirely owned by the coding agent and written via the Ingest Workflow, maintaining index, log, overview, sources, candidates, entities, concepts, projects, and syntheses subdirectories.
- Candidates must pass human-or-agent review before promotion to trusted entity/concept hubs; synthesis alone cannot auto-promote candidates to the knowledge layer.
- The site/ layer is fully generated and safe to delete and regenerate at any time; nothing in it is hand-maintained.
- Pages interlink via wikilinks and contradictions are recorded rather than silently overwritten; pages compound over time as new sources are ingested.

## Key Quotes

> "Everything under `raw/` is treated as source-of-truth. The converter writes to it; nothing else should. If a source is wrong, fix the converter, not the output."
> — Establishes the immutability guarantee that protects the audit trail.

> "Your coding agent owns this layer entirely. It writes via the Ingest Workflow"
> — Clarifies that wiki/ is LLM-maintained, not hand-edited by humans in normal operation.

> "Synthesis alone can leave Home looking 'finished' (Raw → Synthesized) while the knowledge layer is still empty"
> — Identifies the gap between raw ingestion and trusted knowledge; the candidates backlog surfaces this visually.

## Connections

- [[llmwiki]] (entity) — the product whose architecture is documented here
  - fact: Has both a conceptual three-layer model and an eight-layer implementation model.
  
- [[Static Site]] (entity) — the generated output layer (site/) of the architecture
  - fact: Built via `llmwiki build` and is completely regenerable from raw and wiki layers.
  
- [[Knowledge Graph]] (concept) — the trusted hub structure in the wiki/ layer
  - fact: Composed of promoted entities and concepts; candidates remain pending review before joining the graph.
  
- [[Wiki Synthesis]] (concept) — the LLM process that maintains the wiki/ layer
  - fact: Driven by the Ingest Workflow; synthesizes raw documents into sources and candidate stubs.
  
- [[Wikilinks]] (concept) — the linking mechanism that interweaves pages
  - fact: Pages interlink via [[double-bracket]] syntax across wiki/ subdirectories.
  
- [[Adapters]] (entity) — conversion mechanism mentioned in the architecture
  - fact: Convert .jsonl session data to raw/ markdown files, serving as the entry point to the pipeline.

## Contradictions

- None identified. This is architectural documentation; it establishes design rather than reporting empirical findings that could conflict with prior claims.