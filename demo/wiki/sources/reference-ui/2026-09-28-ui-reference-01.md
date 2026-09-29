---
title: "UI reference (part 1/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, site-navigation, home-page-layout, state-visualization, static-site-architecture]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-28
---
## Summary

Technical reference documentation for the UI and navigation structure of the [[llmwiki]] compiled static site (`site/`). Defines the top-level navigation scheme (9 main sections plus Search and Theme toggle), the Home page's queue-first layout (Automation panel, Pipeline state widget, Recent documents), dedicated screens for workflow stages (Raw docs, Candidates review, Knowledge graph, Topics, Projects, Sessions, Analytics, Models, Docs, Prototypes), and the data flow from `llmwiki-state.js` into rendered HTML. Addresses responsive behavior (bottom-nav below 768px) and state persistence (localStorage theme).

## Key Claims

- The Home page is "queue-first" and displays three main sections: Automation settings, Pipeline state tables (Eligible sources and Knowledge layer), and Recent raw documents
- Eligible sources are counted as *documents*, not markdown files—a source that fans out to multiple `wiki/sources/` part-pages contributes a single count
- The Pipeline state widget has five columns: Raw → To synthesize (with USD estimate) → Synthesized (by agent) → On disk; plus Knowledge layer rows for Candidates, Entities, Concepts
- State numbers refresh from `llmwiki-state.js` via `llmwiki sync`, `llmwiki synth --estimate`, successful build/lint, and backfill on version upgrades
- Mobile navigation below 768px width moves the six middle nav links to a persistent bottom bar, keeping Search and Theme toggle in the top bar
- Command palette (⌘K / Cmd+K) searches both wiki-page matches and site pages in two groups

## Key Quotes

> "Queue-first landing page" — describes the Home page design philosophy centered on pipeline workflow visibility

> "a document that fans out into several `wiki/sources/` part-pages still contributes 1" — clarifies that the Eligible sources count represents input documents, not rendered markdown files

> "Numbers come from `llmwiki-state.js` (`synth.pipeline` + `synth.pending` + `synth.estimate` + `ops.*`), refreshed by `llmwiki sync` / `llmwiki synth --estimate` / successful synth and build stamps / lint" — explains the data sources and refresh triggers for state visualization

## Connections

- [[llmwiki]] (entity) — this documentation describes the UI of the llmwiki static site output
  - fact: The site is built by `llmwiki build` into `site/` and consists of plain HTML files
  - fact: Home page surfaces automation status, pipeline state (eligible sources in synthesis workflow), and recent raw documents
  
- [[Static Site]] (entity) — the compiled output these UI screens comprise
  - fact: Navigation includes nine main sections: Home, Raw, Candidates, Graph, Topics, Projects, Sessions, Analytics, Models, Docs, Prototypes
  - fact: Can be published to any static host or opened locally in a browser
  
- [[Wiki Synthesis]] (concept) — the Home Pipeline state widget visualizes the synthesis workflow
  - fact: Shows eligible sources progression: Raw → To synthesize → Synthesized (by agent) → On disk
  
- [[Knowledge Graph]] (concept) — dedicated `/graph.html` screen provides interactive graph visualization
  - fact: Uses vis-network force-directed graph to display interconnected topics

- [[Wikilinks]] (concept) — core to site navigation and link structure
  - fact: Topics on `/topics/index.html` are grouped into curated entities, curated concepts, and derived topics

- [[Lint Rules]] (concept) — Home page displays lint errors when `ops.last_lint_error` is non-empty
  - fact: Lint outcome appears below the state tables in a collapsible section

## Contradictions

None identified.