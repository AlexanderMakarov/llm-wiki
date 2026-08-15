---
title: "CLI reference (part 5/8: synth — synthesize sources + harvest candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, source-synthesis, candidate-harvesting, auto-tagging, synthesis-backend, cost-estimation]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

Documents the `synth` CLI command (#90), which synthesizes pending sources into `wiki/sources/` and harvests entity/concept candidates into `wiki/candidates/` (both by default). The command provides fine-grained control via flags (`--sources-only`, `--candidates-only`, `--sessions-only`, `--docs-only`, `--path`), cost estimation (`--estimate`), and automatic topical tagging without extra API cost. Candidate harvesting is fail-closed: unclassified targets halt the run rather than accepting partial results.

## Key Claims

- The `synth` command is the primary interface (#90); the deprecated `synthesize` alias defaults to `--sources-only` for backward compatibility to prevent existing scripts from unexpectedly writing candidate stubs.
- `--estimate` reports **eligible sources** in the corpus and **current on-disk source pages**, plus `Candidates (pre-run state):` from the existing `wiki/sources/` shape — explicitly **not** a forecast of what the next harvest will yield (#113).
- Auto-tagging produces a `<!-- suggested-tags: ... -->` block as the first response line, rides the synthesis call with no extra API round-trip, and applies stop-word filters, maintainer override, and near-dup rejection (capped at 5 AI tags per page, 0.80 similarity threshold + prefix check).
- Candidate harvesting is fail-closed: any unclassified target stops the run with non-zero exit and writes nothing, rather than allowing partial success.
- Candidate threshold is N **distinct source pages** naming a target (default: 3); the synthesis backend is configurable via `synthesis.backend` in `config.json` or `sessions_config.json` (`dummy`, `ollama`, or `claude`).

## Key Quotes

> "Before the first page is synthesized, a real run announces the batch: `Synthesizing 11 source(s) with ClaudeCLISynthesizer (2 at a time)` — the count is the work queue after up-to-date, ineligible, and already-claimed sources are excluded, so it is what the run will actually do."
— Shows that the batch announcement is an honest count of actual work, not a forecast or estimate.

> "the harvestable shape of `wiki/sources/` **as it exists now**, with a note that pending sources are not yet reflected. It is not a forecast of what the next run will harvest (#113)."
— Clarifies the distinction between reporting current state (what's on disk now) versus predicting future results (after synthesis completes).

> "No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged."
— Confirms that auto-tagging is cost-neutral, bundled into the synthesis budget without additional backend calls.

## Connections

- [[llmwiki]] — the tool/system whose CLI is being documented
- [[Source Synthesis]] — the core synthesis process that populates `wiki/sources/` from raw sources
- [[Candidate Harvesting]] — the harvesting process that derives entity/concept candidates from synthesized sources

## Contradictions

None detected.