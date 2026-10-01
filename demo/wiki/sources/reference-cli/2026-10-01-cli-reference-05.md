---
title: "CLI reference (part 5/19: lint — run registered wiki-quality rules)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, lint, link-integrity, contradiction-detection]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This documentation page comprehensively defines the `llmwiki lint` command, which runs deterministic wiki-quality checks across a wiki directory. It covers command syntax, 10+ command flags (including `--rules`, `--json`, `--fail-on-errors`, `--vault`), and 17+ structural lint rules spanning frontmatter validation, link integrity, orphan detection, freshness, duplicates, contradictions, claims, provenance, staleness, and findability. A significant architectural change (#72) moved `contradiction_detection`, `claim_verification`, and `summary_accuracy` from optional LLM-dependent checks to always-running structural validators with no external dependencies.

## Key Claims

- All lint rules are deterministic; `contradiction_detection`, `claim_verification`, and `summary_accuracy` were refactored from requiring `--include-llm` to always-running structural checks (#72) with no LLM callback wired
- `link_integrity` resolves wikilinks case- and punctuation-insensitively (e.g., `[[LLM-Wiki]]` → `llm-wiki.md`) but not by substring matching, and honors the candidate harvest's significance threshold (#150): zero-mention targets are always reported, sub-threshold targets are deliberate declines and not reported, at-threshold targets with no page are genuine gaps and are reported
- The three findability rules (`page_findability`, `title_ambiguity`, `search_consistency`) share a single corpus scan per lint run to avoid redundant processing
- `orphan_detection` counts inbound wikilinks and catalog markdown links; pages appearing only in `index.md` are not flagged as orphans
- `contradiction_detection`, `claim_verification`, and `summary_accuracy` check for non-filler `## Contradictions` sections, entity/concept claims without sources, and non-empty `summary:` frontmatter respectively; elaborations like "None identified. …" are treated as filler unless they contain unnegated conflict cues
- `provenance_integrity` (#122) emits errors for missing source-summary pages or raw files on pages carrying `sources:` or `source_file:` frontmatter
- `stale_reference_detection` (#87) flags living pages whose dated claims predate the target's `last_updated` field; source pages and `type: source` pages are skipped

## Key Quotes

> "Contradiction detection, claim verification, and summary accuracy used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks: non-filler `## Contradictions` sections, entity/concept claims without sources, and empty `summary:` frontmatter."

This documents a critical refactor where incomplete LLM-dependent rules were replaced with deterministic structural validators, eliminating a broken advertised feature and establishing these rules as core maintenance tools.

> "`link_integrity` resolves targets case- and punctuation-insensitively (`[[LLM-Wiki]]` → `llm-wiki.md`) but does not do substring matching. It honours the candidate harvest's significance threshold (#150): a target named by **no** source page is always reported, a target named **fewer** than `--min-refs` times is a deliberate decline and is not, and a target named **at least** that often with no page of its own is a genuine gap and is."

This articulates a three-tier link validation strategy that catches all truly broken links while filtering noise from incomplete candidate extraction.

## Connections

- [[llmwiki]] (entity) — the wiki system whose lint subcommand this page comprehensively documents
  - fact: Lint is invoked via `python3 -m llmwiki lint` and accepts flags for selective rule execution, JSON output, and exit codes
  - fact: Rules can be disabled per vault in the vault's `llmwiki.json` configuration file
- [[Lint Rules]] (concept) — the direct subject of this entire reference page
  - fact: 17+ deterministic structural rules cover frontmatter, links, orphans, freshness, duplicates, contradictions, claims, summaries, provenance, staleness, and findability
  - fact: Rules like `link_integrity` and `orphan_detection` maintain the integrity of the wiki's [[Knowledge Graph]]
- [[Frontmatter]] (concept) — multiple rules validate frontmatter structure and fields
  - fact: `frontmatter_completeness` and `frontmatter_validity` ensure metadata integrity; `contradiction_detection`, `claim_verification`, and `summary_accuracy` inspect specific frontmatter fields for content validity

## Contradictions

None identified.