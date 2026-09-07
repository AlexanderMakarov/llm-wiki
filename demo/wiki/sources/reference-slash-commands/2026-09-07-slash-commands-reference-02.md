---
title: "Slash commands reference (part 2/4: Wiki pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, wiki-pipeline, llmwiki-cli]
date: 2026-09-07
source_file: raw/docs/reference-slash-commands/slash-commands-reference-02.md
project: reference-slash-commands
model: 
last_updated: 2026-09-07
---
## Summary

This reference documentation describes the wiki pipeline slash commands — `/wiki-init`, `/wiki-sync`, `/wiki-ingest`, `/wiki-synth`, `/wiki-candidates`, `/wiki-query`, `/wiki-update`, `/wiki-lint`, `/wiki-graph`, and `/wiki-reflect`. Each command wraps a corresponding `python3 -m llmwiki` CLI operation and accepts natural-language arguments that Claude translates to CLI flags. Together, these commands implement the core wiki lifecycle: initialization, session ingestion, synthesis, candidate curation, querying, linting, and reflection.

## Key Claims

- `/wiki-init` scaffolds an empty llmwiki by creating `raw/`, `wiki/`, `site/` directories and seeding nine navigation files (`CRITICAL_FACTS.md`, `MEMORY.md`, `SOUL.md`, etc.)
- `/wiki-sync` is the primary ingest mechanism and the **only command that triggers auto-build**; it converts Claude Code sessions to markdown under `raw/sessions/` and ingests them into `wiki/`
- `/wiki-ingest` handles single-document or folder ingestion with candidate review; trusted hubs require explicit promotion via `/wiki-candidates` and do not auto-promote
- `/wiki-synth` performs synthesis via two LLM jobs (known-names prepare + per-file ask), with offline candidate harvesting; `Ctrl+C` during harvest exits 130 and allows granular workflow control
- `/wiki-candidates` triages candidates using `promote`, `flip-promote`, `merge`, and `discard` actions; promotion fills `## Key Facts` offline from source `fact:` bullets
- `/wiki-query` answers questions by reading index + overview + L1 cache_tier pages, with inline wikilinks to source/entity/concept pages
- `/wiki-lint` enforces 16 registered structural/deterministic rules (frontmatter completeness/validity, link integrity, orphan detection, contradiction detection, claim verification, etc.)
- `/wiki-graph` builds a knowledge graph where nodes = wiki pages and edges = wikilinks
- Durable lookback in config (`filters.since` / `adapters.*.since`) applies to `/wiki-sync` when `--since` is omitted
- Natural language arguments are translated to CLI flags (e.g., "sync from this week" → `--since $(date -v-7d +%Y-%m-%d)`)

## Key Quotes

> "only command that triggers auto-ingest of new pages into `wiki/`" — positions `/wiki-sync` as the central ingestion entry point

> "Trusted hubs still require review (`/wiki-candidates` or `llmwiki candidates promote|merge|discard`) — ingest is not an auto-promote escape hatch" — clarifies the staged review process for candidate promotion

> "Ctrl+C harvests from written pages (or prints `synth --candidates-only` after `--sources-only`) and exits 130" — documents interrupt-driven control flow for granular synthesis

> "Prefer the CLI action for the common case" — guidance on when to use `candidates promote` CLI vs. `rewrite-key-facts` LLM workflow

## Connections

- [[llmwiki]] (project) — the wiki system these commands operate on
- [[Claude Code]] (tool) — the interface where these slash commands execute
- [[Codex CLI]] (tool) — the underlying CLI (`python3 -m llmwiki`) wrapped by each command
  - fact: `/wiki-sync` wraps `python3 -m llmwiki sync`
  - fact: `/wiki-lint` wraps `python3 -m llmwiki lint` with 16 registered rules
- [[CLAUDE.md]] (document) — defines the Ingest and Query workflows that slash commands orchestrate
- [[Wikilinks]] (concept) — `/wiki-query` synthesizes answers with inline wikilinks; `/wiki-graph` constructs edges from wikilinks
- [[Knowledge Graph]] (system) — `/wiki-graph` builds the knowledge graph from pages and wikilinks
- [[Wiki Synthesis]] (process) — `/wiki-synth` is the primary automated synthesis operation
- [[Static Site]] (output) — `/wiki-sync` triggers auto-build of site/ HTML files
- [[Configuration Reference]] (document) — contains durable lookback settings for `/wiki-sync` (`filters.since`, `adapters.*.since`)

## Contradictions

None identified. This reference documentation aligns with existing [[llmwiki]] architecture and command signatures.