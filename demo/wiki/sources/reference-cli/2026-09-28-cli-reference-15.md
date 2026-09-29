---
title: "CLI reference (part 15/19: search — literal term or phrase search (#197))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, full-text-search, semantic-search, provenance-tracing, mcp-integration]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

Reference documentation for three core llmwiki CLI commands: `search` performs literal term/phrase character-overlap matching (used by agents via [[MCP Server|entity]]'s `wiki_search` tool); `query` enables semantic knowledge-graph traversal via Graphify; `trace` reveals downward provenance chains from wiki pages to raw transcripts. Each is documented with positional arguments, flags, and usage examples.

## Key Claims

- `search` implements pre-AI-era literal matching: score-weighted character overlap found anywhere in text (no stemming, spelling correction, or semantic understanding)
- `search` is intentionally distinct from `query`: the former does literal character ranking; the latter walks the knowledge graph semantically via Graphify
- `query` requires Graphify (`pip install llm-wiki-plus[graph]`) and a pre-built graph (created via `llmwiki graph`); supports BFS traversal with configurable depth and token budget
- `trace` walks provenance using only frontmatter metadata (`sources:`, `source_file:`); missing hops are marked but do not break the chain
- Search results use centered snippet windows (~400 characters around first hit); term mode returns matching *lines*, phrase mode returns one *page* snippet per hit
- Agents access the search engine via [[MCP Server|entity]]'s `wiki_search` tool, using the same matching engine as the CLI command
- Lint validation rules (`page_findability`, `title_ambiguity`, `search_consistency`) enforce search effectiveness

## Key Quotes

> "Pre-AI-era literal search: score-weighted matching of the characters you type, found anywhere including inside longer words — for example `cat` matches `concatenate`. No stemming, no spelling correction, no meaning-based matching."

Establishes the philosophy of `search` as intentionally pre-semantic and syntactic-only.

> "This is not `query`. `search` ranks pages by literal character overlap; `query` walks the knowledge graph in natural language via Graphify"

Clarifies the deliberate separation of concerns between literal and semantic search.

> "Use `trace` to inspect broken hops; repair them by hand or with `synth` / `migrate broken-provenance` as the lint message suggests."

Shows `trace` as a debugging tool for verifying and repairing provenance chain integrity.

## Connections

- [[llmwiki]] (entity) — core system containing all three commands
  - fact: `search` is exposed to agents via [[MCP Server|entity]]'s `wiki_search` tool
  - fact: `query` requires Graphify extension and pre-built graph
  - fact: `trace` walks provenance chains from wiki to raw transcripts
- [[Knowledge Graph]] (concept) — semantic search substrate
  - fact: `query` performs BFS traversal with depth and budget constraints
  - fact: Graph must be pre-built via `llmwiki graph` before semantic queries
  - fact: Agents access `search` functionality via MCP's `wiki_search` tool using the same matching engine
- [[Wikilinks]] (concept) — search enables discovery of link targets
  - fact: Lint rules (`page_findability`, `title_ambiguity`) ensure wikilinked pages remain discoverable via search ranking

## Contradictions

None identified.