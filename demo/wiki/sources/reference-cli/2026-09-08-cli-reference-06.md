---
title: "CLI reference (part 6/15: synth — synthesize sources + harvest candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, wiki-synthesis, synth-cli, candidate-harvest, known-names, synthesis-concurrency, synthesis-backend, synthesis-estimate]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents `llmwiki synth`, the primary command that by default synthesizes pending raw material into `wiki/sources/` and then harvests entity/concept stubs into `wiki/candidates/`. A full sources pass runs two LLM steps up front (known-names prepare, then one summary job per queued file) plus non-LLM bookkeeping; harvest parses `## Connections` topic bullets from existing source pages and costs zero LLM tokens. The page also spells out flag semantics (`--estimate`, `--candidates-only`, session/doc filters, concurrency, backend overlay), batch progress messaging, Ctrl+C drain behavior (#145), and notes that v1.4.0 removed `--list-pending` / `--complete` in favor of configured synthesis backends.

## Key Claims

- Default `llmwiki synth` runs **both** phases: pending sources → `wiki/sources/`, then candidates → `wiki/candidates/` (#90 / #147).
- A real sources pass uses **two** LLM jobs before per-file work is counted as complete: (1) known-names prepare from wiki on disk (skipped for Dummy / `not is_llm`, which use heuristic vocabulary inject), (2) **one** source-summary ask per queued raw file with a frozen known-names list in the prompt.
- Candidate harvest (including `--candidates-only`) is a **parser** over Connections bullets on `wiki/sources/` — **no** classify LLM call; harvest-alone LLM cost is **zero**.
- `--estimate` reports corpus and “already synthesized” in **eligible source** units (#81), prints on-disk source page file counts separately, and its `Candidates (pre-run state):` block reflects **current** `wiki/sources/` shape — **not** a forecast of the next harvest (#113).
- On Ctrl+C, the CLI drains in-flight pages, then harvests from what was written (unless `--sources-only`, which directs the user to `llmwiki synth --candidates-only`) and exits **130** (#145).
- `--min-refs N` (default 3) gates candidates: a `[[wikilink]]` target becomes a candidate when **N or more distinct source pages** name it.
- `--backend NAME` is a one-run overlay of `synthesis.backend` (`dummy` | `ollama` | `claude` | `cursor_cli`); it does not write `config.json`, and is distinct from session-ingest `cursor_cli` / `cursor_ide` adapters.

## Key Quotes

> "Harvest after sources (and `--candidates-only`) is a parser over those bullets — **no** classify LLM call; cost for harvest alone is **zero** LLM." — Defines the cost model separating synthesis from harvest.

> "`Candidates (pre-run state):` … It is not a forecast of what the next run will harvest (#113)." — Clarifies what `--estimate` does and does not predict.

> "Reads the source layer only — never `raw/` — so it runs no per-source synthesis and **no** classify LLM call" — Scope of `--candidates-only`.

> "**Removed in v1.4.0:** `--list-pending` and `--complete` (agent-delegate pending prompts). Use `synthesis.backend: claude` (or `cursor_cli`) instead." — Migration note for older agent-delegate workflows.

## Connections

- [[llmwiki]] (entity) — CLI and vault pipeline this command belongs to.
  - fact: `synth` is the synthesize entry; known-names prepare runs at the start of each sources pass.
- [[Wiki Synthesis]] (concept) — Automated pass from `raw/` to `wiki/sources/` plus candidate harvest.
  - fact: Default run is sources then harvest; `--sources-only` skips harvest (legacy `synthesize` behaviour).
- [[Ollama]] (entity) — Optional `synthesis.backend` for local generation.
  - fact: `ollama` is listed as a synthesis backend choice alongside `dummy`, `claude`, and `cursor_cli`.
- [[Cursor]] (entity) — `cursor_cli` synthesis backend uses Cursor Agent CLI `agent -p` (default model `composer-2.5`), separate from session-ingest adapters.
  - fact: `--backend cursor_cli` overlays synthesis config for one run without persisting to `config.json`.
- [[Claude Code]] (entity) — `claude` synthesis backend runs synchronous `claude -p`.
  - fact: Replaces removed v1.4.0 `--list-pending` / `--complete` agent-delegate flow when configured as `synthesis.backend: claude`.
