---
title: "Slash commands reference (part 2/4: Wiki pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, wiki-pipeline, lint-rules, wiki-candidates]
date: 2026-09-28
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-28
---
## Summary

This reference document describes the slash commands that orchestrate the [[llmwiki]] pipeline, including init, sync, ingest, synthesis, candidate triage, query, editing, and linting operations. It specifies which Python CLI tools each command wraps, their arguments, use cases, and expected outputs. A major focus is the lint rules subsystem with 20 deterministic quality checks covering frontmatter, links, content freshness, contradictions, and consistency. The document emphasizes that `/wiki-sync` is the only auto-ingest trigger and that candidate promotion requires explicit review via `/wiki-candidates`.

## Key Claims

- `/wiki-sync` is the **only** command that triggers auto-ingest of new pages into `wiki/`
- All 20 lint rules are deterministic and require no LLM execution
- Trusted hubs cannot bypass review — `/wiki-ingest` is not an auto-promote escape hatch; candidates still need `/wiki-candidates` triage
- `/wiki-synth` performs two-stage synthesis: known-names preparation (offline) plus per-file LLM asks for sources, then offline candidate harvest
- Lint rules are ordered deterministically and cover frontmatter, link integrity, orphan detection, content freshness, contradictions, claim verification, and page findability
- `/wiki-query` answers questions by reading `wiki/index.md`, `wiki/overview.md`, `cache_tier: L1` pages, then walking relevant source/entity/concept pages with inline wikilinks

## Key Quotes

> "Also the only command that triggers auto-ingest of new pages into `wiki/`." — `/wiki-sync`'s unique role in the pipeline

> "all deterministic — no LLM" — describing the lint rules subsystem

> "Trusted hubs still require review (`/wiki-candidates` or `llmwiki candidates promote|merge|discard`) — ingest is not an auto-promote escape hatch." — emphasizing that ingestion does not bypass candidate review

> "Do not run a separate consolidate-topics step — known-names prepare is part of `synth`." — architectural note on synthesis stages

## Connections

- [[llmwiki]] (entity) — these slash commands form the primary interface for orchestrating wiki pipeline operations
  - fact: `/wiki-sync` wraps `python3 -m llmwiki sync` and is the sole trigger for auto-ingest
  - fact: `/wiki-lint` wraps `python3 -m llmwiki lint` and runs all 20 deterministic quality checks

- [[Lint Rules]] (concept) — documented extensively with 20 deterministic checks spanning frontmatter, integrity, freshness, and consistency
  - fact: Rules include `frontmatter_completeness`, `link_integrity`, `orphan_detection`, `contradiction_detection`, `claim_verification`, and `page_findability`
  - fact: Lint checks are all offline and do not invoke LLM

- [[Wiki Synthesis]] (concept) — `/wiki-synth` synthesizes raw sessions into `wiki/sources/` and harvests `wiki/candidates/`
  - fact: Synthesis is a two-stage process: known-names preparation plus per-file LLM asks for sources, then offline candidate harvest
  - fact: `Ctrl+C` during harvest exits 130 and can trigger `synth --candidates-only`

- [[Claude Code]] (entity) — the system through which users invoke wiki pipeline slash commands
  - fact: Users orchestrate the entire pipeline through commands like `/wiki-sync`, `/wiki-synth`, `/wiki-candidates`, `/wiki-query` in Claude Code

- [[Wikilinks]] (concept) — used throughout wiki operations and synthesized query results
  - fact: `/wiki-query` answers questions with inline `[[wikilinks]]` linking back to source/entity/concept pages

- [[Obsidian]] (entity) — supported as a vault ingestion destination for `/wiki-sync`
  - fact: `/wiki-sync --vault ~/Documents/Obsidian\ Vault` ingests pages into an Obsidian vault

- [[Static Site]] (entity) — automatically rebuilt after wiki ingestion via `/wiki-sync`
  - fact: Expected output from `/wiki-sync` includes "site/ rebuilt (690 HTML files)"

- [[Knowledge Graph]] (concept) — visualized and queried through the `/wiki-graph` command (partially documented)

## Contradictions

None identified. This is a reference document describing existing command interfaces and lint rules without contradicting prior claims.