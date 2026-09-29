---
title: "UI reference (part 7/8: Command palette (⌘K))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, command-palette, search-ui, faceted-search, wiki-search]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-29
---
## Summary

Documents the command palette feature (⌘K) of the deployed llm-wiki website, specifying the search algorithm (literal substring matching, case-insensitive), result grouping (Wiki vs Site with separate algorithms), filtering and faceting capabilities, and keyboard interaction. The palette preserves unlinked pages for completeness while applying distinct search semantics to wiki and site content.

## Key Claims

1. The command palette uses literal substring matching (case-insensitive) rather than fuzzy scoring; a multi-word query must appear as an exact substring to return results, aligning search with assistant expectations rather than providing best-guess results.

2. Results split into Wiki and Site groups with separate search algorithms: Wiki group runs the same algorithm as `wiki_search` mode=match; Site group searches all non-wiki content (static pages, projects, sessions, documents, editorial docs, slash commands, topic pages).

3. Wiki pages without corresponding reader pages (e.g., `wiki/overview.md`, `candidates/`, `syntheses/`) are listed with paths and matching lines but are non-clickable, preserving coverage of assistant-accessible content while preventing navigation dead ends.

4. Search results are capped at 200 pages and 200 matching lines per group; the line cap typically trips first, after which only name matches can add new pages to results.

5. Faceted filtering supports Project, Entity type, Lifecycle, Confidence, and Tags; structured filters (`type:`, `project:`, `model:`, `date:`, `tags:`, `sort:`) apply to Site group only, while `kind:` filter applies to both.

## Key Quotes

> "These semantics replaced the palette's earlier fuzzy scoring for wiki results, so a query of several words that appears nowhere as a literal string returns nothing rather than a best guess; matching what an assistant answers means matching it exactly."

Explains the design philosophy: search should return results that align with what an assistant would actually match, not provide approximations.

> "A wiki page the site has no reader page for — `wiki/overview.md`, `wiki/log.md`, `candidates/`, `syntheses/`, `categories/` — is still listed with its path and lines but is **not** clickable, and `↑ / ↓` step over it. That is how the group keeps the assistant's full coverage without offering dead ends."

Shows deliberate handling of unlinked content: maintaining search completeness while avoiding broken navigation.

> "A capped group routinely reports *fewer* than 200 pages — the line cap trips first, and from then on only a name match can still admit a page."

Clarifies cascading constraints: line-count limits typically bind before page-count limits.

## Connections

- [[llmwiki]] (entity) — the system whose command palette search UI is documented
  - fact: The palette implements the primary search and navigation interface for the deployed website.

- [[Static Site]] (concept) — the palette searches both wiki and static site content
  - fact: Site group returns static pages, projects, sessions, documents, editorial docs, slash commands, and topic pages alongside wiki results.

- [[Wiki Synthesis]] (concept) — wiki page indexing and search are components of the synthesis pipeline
  - fact: The Wiki group uses the same search algorithm as `wiki_search` mode=match over the synthesis corpus.

- [[MCP Server]] (entity) — the `wiki_search` algorithm exposed through the MCP contract powers the palette
  - fact: Command palette's Wiki group implements the same matching semantics as the synthesis pipeline's `wiki_search` interface.

- [[Knowledge Graph]] (concept) — faceted navigation enables exploration of semantic structure
  - fact: Facet filtering by Project, Entity type, Lifecycle, Confidence, and Tags allows users to navigate the topic graph.