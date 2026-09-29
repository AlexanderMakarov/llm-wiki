---
title: "UI reference (part 2/8: Candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-ui, candidates-review, static-site-ui, models-index, knowledge-graph-ui]
date: 2026-09-28
source_file: 
project: reference-ui
model: 
last_updated: 2026-09-28
---
## Summary

This technical reference documents the web UI and page layouts for [[llmwiki]] (entity)'s static site, with detailed emphasis on the candidates review interface (`/candidates.html`), where users can promote, merge, or discard pending entities and concepts through a browser-based decision workflow. Also describes project index, session index, and models reference pages, including sorting, filtering, auto-synthesis of summaries, and activity visualization.

## Key Claims

- The candidates review interface uses **browser-local state**—all decisions are stored in the UI session, nothing runs or is sent to the server until the "Apply" button is clicked.
- **Merge targets are a closed set** determined by `merge --into` resolution: trusted pages under `wiki/<kind>/` first, then same-table pending stubs. Invalid merge targets are rejected before batching.
- **Discard actions require a reason** (stored alongside the archived stub), and optionally allow redirecting links to an existing page. A discard with no reason or unresolved merge target is held back from batch execution.
- **Half-finished reviews can be applied incrementally**: a row left at "No decision" stays pending and can be resumed after a partial batch is applied.
- **Project detail pages auto-synthesize summaries** from their constituent sessions and display "Connected topics" co-occurrence counts (omitted if no topic connections exist or graph is unavailable).
- **Session detail pages include auto-synthesized key claims and key quotes** pulled from the conversation transcript.
- **Sessions table supports multi-dimensional filtering**: project, agent, model, date range, and slug substring; filter state persists in `sessionStorage` for the browser tab.

## Key Quotes

> "Merge into…" reveals a **filterable dropdown** of every page `merge --into` resolves for that table — the trusted pages under `wiki/<kind>/` first, then the same-table pending stubs. Press the ▾ button or `↓` to browse the whole list without typing, type any part of a name to narrow it (case-insensitive substring)...

This shows the constrained, validated UI for merge target selection.

> A row left at **No decision** is absent from the batch and stays pending, so a half-finished review can be applied and resumed.

Demonstrates the incremental workflow design—reviews need not be completed in one session.

> `llmwiki candidates apply` rebuilds `site/` after a successful batch, so reload the page (or reopen the file) to see the remaining queue.

Clarifies the rebuild-after-apply contract between the web UI and CLI.

## Connections

- [[llmwiki]] (entity) — the wiki system whose UI and pages are documented here.
  - fact: Provides CLI actions (`candidates apply`, `merge`, `discard`) that are mirrored in the web UI with browser-local state and batch operations.
- [[Static Site]] (entity) — the generated website containing all documented pages.
  - fact: Includes candidates review page, project index and detail cards, session table and detail pages, and models reference with structured info cards.
- [[Knowledge Graph]] (concept) — displayed on project detail pages via "Connected topics" section.
  - fact: Shows co-occurrence counts and bidirectional links between topics and projects.
- [[Wiki Synthesis]] (concept) — underpins the auto-generated summaries and key claims on session and project pages.
  - fact: Session and project detail pages auto-synthesize 2–4 sentence abstracts and key claims extracted from transcripts.

## Contradictions

None identified.