---
title: "UI reference (part 2/6: Candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, ui-reference, candidates-workflow, project-discovery, sessions-index, models-reference]
date: 2026-09-07
source_file: raw/docs/reference-ui/ui-reference-02.md
project: reference-ui
model: 
last_updated: 2026-09-07
---
## Summary

Documented six key UI pages in the [[llmwiki]] [[Static Site]]: the Candidates review gate (`/candidates.html`), Projects index and detail pages, Sessions index and detail pages, and Models reference. Specified layout, functionality, and interaction patterns for each page, with emphasis on the Candidates page's browser-state workflow and pinned Apply bar for batching reviewer decisions.

## Key Claims

- The Candidates page at `/candidates.html` is a review gate for pending stubs under `wiki/candidates/`, offering per-row decisions (Promote, Flip and promote, Merge into…, Discard) that live in browser state until Apply is clicked, allowing incomplete reviews to be resumed.
- The Apply bar remains pinned under the site nav and shows the assembled command and JSON batch that can be copied directly (`llmwiki candidates apply --vault <vault> --actions -`).
- Merge targets in the Candidates UI are resolved from `wiki/<kind>/` trusted pages plus same-table pending stubs, presented as a filterable dropdown that narrows on substring match (case-insensitive).
- Project detail pages show "Connected topics" — topics the project co-occurs with — positioned above session tables, routing to topic or project pages depending on the neighbour type.
- Sessions index includes a SVG sparkline activity timeline across the calendar span with interactive hover/focus/click labels, filter bar (Project, Agent, Model, date range, slug substring), and persistent filter state via `sessionStorage`.
- Models page displays structured info cards per `ModelProfile`: provider, release date, context/output limits, modalities, pricing per 1M tokens (input, cached, output), and benchmark scores (GPQA Diamond, SWE-bench, MMLU, LiveCodeBench).

## Key Quotes

> "Deciding is browser state, so nothing runs and nothing is sent." — Decisions in the Candidates UI are entirely client-side until the Apply button is pressed, enabling partial reviews to be saved and resumed.

> "A row left at **No decision** is absent from the batch and stays pending, so a half-finished review can be applied and resumed." — The workflow explicitly supports incremental review completion.

> "the topics this project co-occurs with, immediately above the session tables. Same list shape as on a topic page…and each entry routes exactly as it does everywhere else" — Connected topics navigation is consistent across all pages, supporting both topic and project routing.

## Connections

- [[llmwiki]] (system) — the entire UI reference documents pages in the llmwiki static site generator.
- [[Static Site]] (concept) — all six pages (Candidates, Projects, Sessions, Models) are generated HTML output deployed to GitHub Pages.
- [[Knowledge Graph]] (concept) — project detail pages display "Connected topics" computed from co-occurrence in the topic graph.
- [[Wikilinks]] (concept) — session detail pages contain `[[wikilinks]]` references to entities, concepts, and related sessions.
- Candidates workflow (workflow) — review gate for pending stubs with browser-state decisions and pinned Apply bar; supports Promote, Flip and promote, Merge into, Discard actions.
- Session discovery (pattern) — sessions index provides sortable table, activity timeline, and persistent filterbar; session detail shows frontmatter, summary, claims, quotes, transcript, connections.

---

*This entry documents part 2/6 of the UI reference series, focusing on candidate review, project discovery, sessions index, and models reference pages.*