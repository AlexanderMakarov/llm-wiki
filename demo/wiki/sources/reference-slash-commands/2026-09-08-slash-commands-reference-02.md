---
title: "Slash commands reference (part 2/4: Wiki pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, wiki-pipeline, wiki-sync, candidate-review, lint-rules, wiki-lint]
date: 2026-09-08
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents the **wiki pipeline** slash commands (`/wiki-init` through `/wiki-reflect`): what each command does, which CLI or `CLAUDE.md` workflow it wraps, and when to use it. It clarifies that `/wiki-sync` is the sole path that both converts agent sessions into `raw/` and auto-ingests into `wiki/`, while `/wiki-ingest` and `/wiki-synth` split manual or bulk synthesis from candidate harvest. Candidate triage stays gated behind `/wiki-candidates` or `llmwiki candidates` actions even after ingest.

## Key Claims

- `/wiki-sync` wraps `python3 -m llmwiki sync` and is the only slash command that triggers auto-ingest of new material into `wiki/` (and may auto-rebuild `site/` per the narrated example).
- When `--since` is omitted on sync, durable lookback from config (`filters.since` / `adapters.*.since`) applies on a bare `/wiki-sync`.
- `/wiki-ingest` follows the Ingest Workflow in `CLAUDE.md` and does **not** auto-promote trusted hubs; review via `/wiki-candidates` or `llmwiki candidates promote|merge|discard` is still required.
- `/wiki-synth` wraps `llmwiki synth` with two LLM jobs per run for sources (known-names prepare plus one ask per queued file); harvest is offline, and known-names prepare is part of `synth`—not a separate consolidate-topics step.
- Interrupting `synth` with Ctrl+C harvests from pages already written (or, after `--sources-only`, suggests `synth --candidates-only`) and exits with code 130.
- `/wiki-lint` wraps `llmwiki lint` over all registered structural rules (16 at last count; live count from `llmwiki lint --help`), including `index_sync`, `stale_candidates`, and `tags_topics_convention` (G-16 · #302).
- `llmwiki candidates` promote can fill empty `## Key Facts` offline from source `fact:` bullets and harvest stubs; Dummy / no backend is sufficient for the common promote path (#147).
- `/wiki-graph` emits `graph/graph.json` and `graph/graph.html`; build copies graph HTML into `site/` for browser viewing.

## Key Quotes

> "Trusted hubs still require review (`/wiki-candidates` or `llmwiki candidates promote|merge|discard`) — ingest is not an auto-promote escape hatch." — boundary between ingest and candidate promotion

> "Do not run a separate consolidate-topics step — known-names prepare is part of `synth`." — how topic consolidation fits the synth pipeline

> "Also the only command that triggers auto-ingest of new pages into `wiki/`." — role of `/wiki-sync` in the pipeline

## Connections

- [[llmwiki]] (entity) — command surface for init, sync, synth, lint, graph, and static output
  - fact: `/wiki-init` scaffolds `raw/`, `wiki/`, `site/` and seeds index, log, overview, and nine navigation files.
- [[Wiki Synthesis]] (concept) — `/wiki-synth`, ingest-driven source pages, and offline candidate harvest
  - fact: Default synth path writes `wiki/sources/` then harvests into `wiki/candidates/` unless `--sources-only` is used.
- [[Adapters]] (concept) — `/wiki-sync` converts Claude Code, Codex, Cursor, and other adapter stores into `raw/sessions/`
- [[CLAUDE.md]] (concept) — defines Ingest and Query workflows wrapped by `/wiki-ingest` and `/wiki-query`
- [[Wikilinks]] (concept) — `/wiki-query` answers with inline `[[wikilinks]]`; `/wiki-update` fixes links without re-ingest
- [[Knowledge Graph]] (concept) — `/wiki-graph` builds nodes and edges from wikilinks into `graph/graph.json` and `graph/graph.html`
- [[Static Site]] (concept) — narrated sync output includes optional auto-build of `site/` (e.g. hundreds of HTML files)
- [[Obsidian]] (entity) — example vault target for `/wiki-sync` in natural-language invocations
