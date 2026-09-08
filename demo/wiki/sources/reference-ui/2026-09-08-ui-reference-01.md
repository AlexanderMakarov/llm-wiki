---
title: "UI reference (part 1/6)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, static-site-ui, pipeline-state-widget, command-palette, candidates-review, site-navigation, llmwiki-state]
date: 2026-09-08
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-08
---
## Summary

Part 1 of the UI reference maps the compiled wiki site (`llmwiki build` → `site/`) and documents shared top navigation plus the Home landing page. It defines what each nav item surfaces (pipeline state, raw tree, candidates review, graph, projects, sessions, analytics, models, docs, prototypes) and how Search (`⌘K`) and theme persistence work. Home is described as queue-first: an Automation panel from `.llmwiki/automation-status.json`, a dual-table Pipeline state widget fed by `llmwiki-state.js`, collapsible backlog sections, and recent `raw/docs/` entries—with explicit counting rules that separate eligible synthesis inputs from on-disk `wiki/sources/` files and pending `wiki/candidates/` from pre-run harvest estimates.

## Key Claims

- Every compiled page shares the same header navigation; `⌘K` opens a fuzzy command palette over the full corpus, and theme choice persists in `localStorage.theme`.
- The Home **Eligible sources** columns count synthesize inputs (one eligible source per document even when it fans out to multiple `wiki/sources/` part-pages); the fifth **On disk** column counts `.md` files under `wiki/sources/` with separate session, Documents, Stubs, and Other rows.
- The **Candidates** count on Home reflects stubs already under `wiki/candidates/`, not the `Candidates (pre-run state):` figure from `synth --estimate`, which describes harvestable state from current `wiki/sources/` before pending sources are synthesized.
- Below 768px, the six middle nav links move to a bottom bar while Search and Theme stay in the top bar.
- Home’s Automation block is settings-only (job, schedule, synth backend hint, hooks, watch, last-run log); it deliberately omits pipeline stage timestamps, lint outcome, and lint-fail policy reminders per issue #234.

## Key Quotes

> "Every screen on the compiled site (`llmwiki build` → `site/`), what it shows, and how to reach it. The site is plain files — open `site/index.html` in a browser, or publish `site/` to any static host." — framing for the whole UI reference series.

> "The first three columns count **eligible sources** (synthesize inputs), not markdown files or wiki pages — a document that fans out into several `wiki/sources/` part-pages still contributes 1 (#81)." — core semantics for interpreting Home pipeline numbers.

> "**Candidates** counts pending stubs already under `wiki/candidates/` (not the `Candidates (pre-run state):` harvestable figure from `synth --estimate`…)" — disambiguates two different candidate metrics users might confuse.

## Connections

- [[llmwiki]] (entity) — product whose built `site/` screens and state sidecar this reference documents.
  - fact: `llmwiki build` recounts candidates and trusted entity/concept pages and copies state into `site/llmwiki-state.js`.
- [[Static Site]] (concept) — plain-file HTML output, top nav, and mobile layout behavior for the wiki.
  - fact: Navigation URLs are paths like `/index.html`, `/graph.html`, `/candidates.html` on the generated site.
- [[Wiki Synthesis]] (concept) — pipeline stages and counts shown on Home (Raw → To synthesize → Synthesized, estimates, queue queued/in progress).
  - fact: State refreshes from `llmwiki sync`, `llmwiki synth --estimate`, successful synth/build stamps, and lint JSON sidecar—not from lint rewriting HTML.
- [[Knowledge Graph]] (concept) — reachable via **Graph** (`/graph.html`) as an interactive force-directed view (vis-network).
- [[Wikilinks]] (concept) — implied by the knowledge layer (Entities / Concepts) and cross-linked wiki content the site represents; this part focuses on shell UI rather than link resolution rules.
