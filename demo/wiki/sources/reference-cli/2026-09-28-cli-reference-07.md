---
title: "CLI reference (part 7/19: synth — synthesize sources + harvest candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, synth-command, source-synthesis, candidate-harvest, usage-limits]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

The `synth` command synthesizes wiki sources and harvests entity/concept candidates in two phases: (1) known-names vocabulary preparation once per run (~1 min), then (2) individual source-summary LLM calls. Candidates harvest is offline, parsing only Connection bullets with zero LLM cost. The command supports granular phase control via flags, handles backend usage limits via clean-stop with deferred retries (#145/#181), and provides exit codes indicating success, failure, usage limit (75), or interrupt (130).

## Key Claims

- `synth` runs two sequential language-model jobs: known-names preparation once per sources pass, then individual source-summary asks per queued file
- Candidates harvest is offline and requires zero LLM calls, only parsing Connection bullets into wiki/candidates/
- Backend usage limits trigger a clean stop (#145/#181) that cancels new work, finishes in-flight pages, defers unstarted sources, and exits with code 75
- Pages lacking only kind labels on Connections should use `llmwiki migrate topic-kinds` (#174) instead of full re-synth to avoid costs
- Exit codes: 0 (success), 1 (failure), 2 (usage error), 75 (usage limit), 130 (Ctrl+C)

## Key Quotes

> "A real sources pass is **two language-model jobs**, then bookkeeping: (1) prepare known-names once at the start of the run... (2) **one** source-summary ask per queued raw file, with that frozen list in the prompt" — establishes the two-phase architecture

> "The later offline **candidates harvest** (after sources, or `synth --candidates-only`) only parses those Connections bullets into `wiki/candidates/` — **no** classify LLM call; harvest cost alone is **zero** LLM." — clarifies that candidate extraction requires no additional model invocations

> "A usage-limit stop prints one line... Sources that did not run are **deferred**, not errors: they stay pending and the next run picks them up." — explains deferred retry behavior for interrupted runs

## Connections

- [[llmwiki]] (entity) — the project providing the synth command
  - fact: synth is the primary synthesize entry (#90, #147)
  - fact: runs two sequential LLM jobs with frozen vocabulary prep at the start of each sources pass
- [[Wiki Synthesis]] (concept) — the wiki content generation process
  - fact: known-names preparation builds vocabulary once per run to populate the source-summary prompts
  - fact: candidates harvest only parses Connection bullets, requiring zero LLM cost
- [[Codex CLI]] (entity) — the command-line tool providing the synth entry point
  - fact: invoked as `python3 -m llmwiki synth` with phase control flags (--sources-only, --candidates-only, --force)
- [[Ollama]] (entity) — one of three supported backend systems
  - fact: recognized as a backend option alongside Claude CLI and Cursor Agent CLI

## Contradictions

None identified. This is reference documentation establishing command behavior without conflicts to prior content.