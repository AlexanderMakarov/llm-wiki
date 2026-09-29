---
title: "CLI reference (part 5/19: lint — run registered wiki-quality rules)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, lint-rules, wikilink-resolution, findability-search, provenance-integrity]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

CLI reference for the `lint` command, which runs 20+ deterministic wiki-quality validation rules covering frontmatter integrity, link resolution, orphan detection, content freshness, and search findability. Key architectural shifts: contradiction/claim/summary checks now run as structural rules (#72); link resolution ignores case and punctuation; findability rules use shared corpus scoring with the search command.

## Key Claims

- All lint rules are deterministic (no LLM involvement)
- Link integrity resolves targets case- and punctuation-insensitively but does not do substring matching
- `orphan_detection` counts inbound wikilinks and catalog markdown links; pages listed only in index.md are not orphans
- `contradiction_detection`, `claim_verification`, and `summary_accuracy` run as structural checks as of #72, checking for non-filler sections and missing frontmatter
- `stale_reference_detection` flags living pages whose dated claims predate the target's `last_updated`
- Findability rules share one corpus scan per lint run with the search command, enabling consistent ranking

## Key Quotes

> "All rules are deterministic (no LLM)." — Establishes that lint output is reproducible and machine-independent.

> "`contradiction_detection`, `claim_verification`, and `summary_accuracy` used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks" — Documents the shift from planned LLM integration to deterministic validation.

> "Filler bodies like `None identified.`, `None detected.`, and multi-sentence `None identified. …` elaborations are not findings" — Clarifies how structural checks treat negation and empty report sections.

## Connections

- [[Lint Rules]] (concept) — The central topic; this document is the comprehensive reference manual
  - fact: 17+ deterministic structural rules plus 3 findability rules cover frontmatter, links, content freshness, duplicates, and consistency
  - fact: As of #72, contradiction/claim/summary checks run as structural validation (no LLM callback ever implemented)

- [[llmwiki]] (entity) — The CLI tool implementing lint validation
  - fact: Invoked via `python3 -m llmwiki lint` with configurable rule selection and exit codes for CI/CD gating

- [[Wikilinks]] (concept) — Primary subject of the link_integrity rule
  - fact: Resolved case- and punctuation-insensitively but not with substring matching; honours candidate harvest's significance threshold

- [[Knowledge Graph]] (concept) — Multiple rules ensure graph integrity and reachability
  - fact: orphan_detection counts inbound wikilinks and markdown links to identify unreachable pages

- [[Static Site]] (entity) — Lint validates quality before site generation
  - fact: --fail-on-errors and --fail-on-warnings enable CI/CD build gating on rule severity