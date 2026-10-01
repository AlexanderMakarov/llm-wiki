---
title: "CLI reference (part 15/19: search — literal term or phrase search (#197))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, literal-search, semantic-search, knowledge-graph, provenance-tracking]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

The session documents three CLI subcommands for vault introspection: `search` for literal term/phrase matching (no stemming or semantic interpretation), `query` for natural-language knowledge-graph walks via Graphify, and `trace` for walking page provenance back to raw transcripts. Each command supports different input modes, filtering, and formatting options, with defined exit codes and error-handling contracts.

## Key Claims

1. The `search` subcommand performs score-weighted literal character matching (no stemming/spelling correction), distinct from `query` which traverses the knowledge graph semantically
2. `search` has two modes: `term` (returns matching lines) and `phrase` (returns page-level results), both using the same ~400-character snippet window via `extract_snippet`
3. `query` requires Graphify extension (`pip install llm-wiki-plus[graph]`) and performs BFS traversal of the knowledge graph with configurable depth (default 3) and token budget (default 2000)
4. `trace` uses only frontmatter fields (`sources:`, `source_file:`) to build provenance chains, marking missing hops but still completing successfully
5. All commands exit code 0 on successful execution (including zero results); `trace` uses exit codes 0/1/2 to distinguish completion states and fatal errors

## Key Quotes

> "Pre-AI-era literal search: score-weighted matching of the characters you type, found anywhere including inside longer words — for example `cat` matches `concatenate`. No stemming, no spelling correction, no meaning-based matching."

Establishes the fundamental design of literal search as character-level matching without semantic interpretation.

> "This is not `query`. `search` ranks pages by literal character overlap; `query` walks the knowledge graph in natural language via Graphify."

Clarifies the key architectural distinction between the two search approaches and their intended use cases.

> "Bulk runs group hits per entry and state which entries returned nothing. Always exits `0` on a successful search (including zero hits)."

Defines the API contract for bulk operations and error handling, important for automation and scripting.

> "Walk a wiki page's encoded chain to its source summaries and raw files. Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts. Missing hops are marked; the walk still succeeds."

Explains `trace`'s limited scope and graceful degradation strategy for incomplete provenance chains.

## Connections

- [[llmwiki]] (entity) — the CLI tool containing these three subcommands
  - fact: `search`, `query`, and `trace` are documented as part of the main llmwiki CLI reference (part 15 of 19).

- [[Knowledge Graph]] (concept) — the semantic structure that `query` traverses
  - fact: The `query` subcommand performs BFS traversal of the knowledge graph with configurable depth and token budget.

- [[Graphify]] (entity) — the extension providing semantic knowledge-graph queries
  - fact: Semantic queries require Graphify (`pip install llm-wiki-plus[graph]`); users must run `llmwiki graph` to build the graph first.

- [[MCP Server]] (entity) — exposes literal search functionality to agents
  - fact: The same literal character-matching engine that `search` uses is available to agents via the MCP `wiki_search` tool.

- [[Frontmatter]] (concept) — metadata structure enabling provenance tracing
  - fact: The `trace` command uses only frontmatter fields (`sources:`, `source_file:`) to build provenance chains without inspecting page body text.

## Contradictions

None identified.