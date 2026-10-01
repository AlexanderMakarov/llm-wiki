---
title: "CLI reference (part 7/19: synth — synthesize sources + harvest candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, source-synthesis, candidate-harvesting, clean-stop, known-names-preparation]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Documents the `synth` command, the primary CLI entry for [[llmwiki]], which synthesizes queued sources into wiki pages via two phases: source summary synthesis (via LLM) and entity/concept candidate harvesting (offline parsing of Connections bullets). The command implements graceful shutdown on Ctrl+C or backend usage limits, deferring unstarted sources while letting in-flight pages complete, and provides specific exit codes for success, failure, usage limits, and interruption.

## Key Claims

- `synth` default runs both phases: known-names preparation, source synthesis, then candidates harvesting; phases are distinct LLM jobs and offline parsing respectively.
- Known-names preparation (Job 1) runs once per sources pass, building a vocabulary of existing topics (with entity/concept kind) to inject frozen into each source-summary LLM prompt, reducing the size of shared context.
- Candidates harvesting is a separate offline phase that only parses Connections bullets from already-written pages into `wiki/candidates/`, costing zero LLM tokens.
- Ctrl+C or backend usage limit stops trigger a clean stop: pending (unstarted) sources are deferred, pages already in flight complete, a single log entry marked `stopped early` is recorded with a deferred count, and candidates are harvested unless `--sources-only`.
- Exit codes are: `0` (success), `1` (source or harvest failed), `2` (usage error), `75` (backend usage limit; retry after reset), `130` (Ctrl+C).
- `--estimate` records vault state (pending list, pipeline rows, estimate block) in `llmwiki-state.json` without calling any backend or touching pages.
- The batch announcement (`Synthesizing N source(s)`) appears before synthesis starts and reflects only the work queue after filtering out up-to-date, ineligible, and claimed sources.

## Key Quotes

> "A real sources pass is **two language-model jobs**, then bookkeeping: (1) prepare known-names once at the start of the run (canonical name, aliases, kind, short description) from wiki already on disk… (2) **one** source-summary ask per queued raw file, with that frozen list in the prompt." — clarifies that known-names prep and source synthesis are distinct LLM tasks separated from offline candidates harvesting.

> "Pages that only lack usable `(entity)` / `(concept)` labels on Connections — and whose targets already have matching wiki filings — should use `llmwiki migrate topic-kinds` for label-only catch-up (#174), not a full paid re-synth." — identifies a cost-saving path for label-only corrections.

> "Sources that did not run are **deferred**, not errors: they stay pending and the next run picks them up." — emphasizes that clean stops preserve work for retry rather than abandoning sources.

## Connections

- [[llmwiki]] (entity) — the wiki system that synth serves
  - fact: `synth` is the primary command (#90 / #147) for synthesizing raw sources into wiki pages
- [[Wiki Synthesis]] (concept) — the methodology synth implements
  - fact: Known-names preparation (Job 1) builds a vocabulary of existing topics to inject into source-summary LLM prompts
  - fact: Candidates harvesting is a separate offline phase parsing Connections bullets into `wiki/candidates/`, costing zero LLM calls
- [[Knowledge Graph]] (concept) — where harvested candidates populate
  - fact: Connections bullets on source pages name topics with entity/concept kind and nested fact claims