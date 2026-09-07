---
title: "UI reference (part 1/6)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, ui-reference, navigation, pipeline-state, static-site]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-01.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

Documents the complete UI structure of the compiled [[llmwiki]] [[Static Site]], including the top navigation bar, nine main pages, and the home page's Pipeline State widget. The Pipeline State widget displays synthesis pipeline progress (Raw → To synthesize → Synthesized by agent) and knowledge layer status (Candidates → Entities/Concepts), powered by synth.pipeline data refreshed during `llmwiki build` and `llmwiki sync` operations.

## Key Claims

- The llmwiki site is delivered as plain static files in `site/`, opened locally or published to any static host without a server requirement
- The home page Pipeline State widget counts eligible sources as logical documents, not markdown files—a multi-part source contributes one count regardless of `.md` file count (#81)
- The table tracks five pipeline stages: Raw (input), To synthesize (with estimated USD cost), Synthesized (by agent attribution), and On disk (with stubs and orphans), plus a Knowledge layer row for Candidates and Entities/Concepts
- Mobile navigation collapses the six core nav links into a bottom-nav below 768px viewport; Search (⌘K) and Theme toggle remain in the top bar
- The command palette (⌘K) provides fuzzy-search across the entire corpus from any page
- Pipeline State data originates from `llmwiki-state.js`, updated by `llmwiki sync` and `llmwiki synth --estimate`, with counts backfilled on each `llmwiki build`

## Key Quotes

> "The site is plain files — open `site/index.html` in a browser, or publish `site/` to any static host."
— Establishes the deployment model: outputs are portable static files with no server dependency.

> "The first three columns count eligible sources (synthesize inputs), not markdown files or wiki pages — a document that fans out into several `wiki/sources/` part-pages still contributes 1 (#81)."
— Clarifies the Pipeline State widget's counting semantics to prevent confusion with file-level counts.

## Connections

- [[llmwiki]] (project) — the primary system; all nine pages and navigation are part of its static site
  - fact: The home page serves as the pipeline queue-first landing page with state and recent-docs sections
- [[Static Site]] (system) — the output format (`site/`) is portable static HTML/JS deployable anywhere
  - fact: Generated via `llmwiki build` and supports both local browsing and publishing to static hosts
- [[Knowledge Graph]] (feature) — `/graph.html` displays an interactive force-directed graph using vis-network
  - fact: Connected to the Pipeline State widget's Knowledge layer (Entities/Concepts counts)
- [[Wiki Synthesis]] (process) — the Pipeline State widget visualizes synthesis pipeline stages and is refreshed by `llmwiki synth --estimate`
  - fact: Eligible source counts are updated during `llmwiki build` and `llmwiki sync` operations

## Contradictions

None identified.