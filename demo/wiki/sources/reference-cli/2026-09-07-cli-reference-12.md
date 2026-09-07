---
title: "CLI reference (part 12/15: all — run the full pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, pipeline-orchestration, session-polling]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-12.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This CLI reference documents two primary commands in the [[llmwiki]] system: **`all`** — a unified orchestrator that runs the full pipeline (sync → synth → build → graph → lint) with granular control over each stage and lint failure policies, and **`watch`** — a polling daemon that detects finished sessions across multiple [[Adapters]] and automatically triggers maintain operations with strict single-flight semantics.

## Key Claims

- The `all` command executes a deterministic sequence: sync → synth → build → graph → lint, designed as the primary entry point for scheduled jobs
- Every stage in `all` can be independently disabled (--no-sync, --no-synth, --skip-graph, --skip-lint) or modified with stage-specific flags
- [[Wiki Synthesis|Synth]] is the only stage capable of LLM calls; with the default dummy backend, no provider is invoked
- The `build` stage handles AI-consumable exports (`llms.txt`, `sitemap.xml`) as built-in functionality, not a separate step
- `watch` enforces strict single-flight semantics: only one maintain iteration runs at a time; changes arriving during a run are deferred via dirty flag and retried after completion
- `watch` uses per-adapter completion heuristics (Claude's `stop_reason`, Cursor's last role, Codex events) rather than a uniform timeout
- Adapters without native finished-signal support fall back to 2-second mtime settle instead of multi-minute quiescence
- The `--lint-fail` policy controls pipeline failure: `never` (default), `errors`, or `warnings`

## Key Quotes

> "The one command to run after agent sessions land. It runs every stage in order — `sync` → `synth` → `build` → `graph` → `lint`"

Establishes `all` as the canonical orchestration command for post-session workflows.

> "Single-flight: only one maintain iteration at a time (`sync` → `synth` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes."

Defines the concurrency guarantee and retry model for `watch`.

## Connections

- [[llmwiki]] (project) — primary system whose CLI this documents
- [[Adapters]] (concept) — `watch` dynamically loads and monitors multiple coding-agent sources
- [[Wiki Synthesis]] (concept) — describes synth as the sole LLM-calling stage and notes the dummy backend makes no provider call

## Contradictions

None detected. The documentation is internally consistent and aligns with prior session notes regarding synth's role in the pipeline.