---
title: "CLI reference (part 16/19: all — run the full pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, pipeline-orchestration, exit-codes, synthesis-backends, lint-failure-policy]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

The `llmwiki` CLI provides two main commands for maintaining the knowledge base: `all` orchestrates a five-stage pipeline (sync → synth → build → graph → lint) with independent opt-out flags for each stage, while `watch` polls adapters for finished sessions and runs maintenance on a configurable interval. The pipeline handles optional LLM synthesis, preserves build artifacts even on lint failures, and reports detailed exit codes to inform CI/CD systems and operators about what happened.

## Key Claims

- The `all` command is the intended entry point after agent sessions complete, running every pipeline stage in sequence with per-stage opt-out flags.
- `synth` is the only pipeline stage that can call an LLM; it defaults to a dummy backend that makes no API calls, so LLM invocation is opt-in rather than automatic.
- Exit codes differentiate success (0), step failure (1), lint policy breach (2), backend usage limits (75), and user interruption (130).
- When `--lint-fail` triggers a run failure, the preceding build's HTML is preserved in `site/`; lint does not revert output, and the home page reports the failure via Pipeline state.
- By default, later pipeline stages run even if earlier stages fail; `--fail-fast` stops at the first error.
- The `watch` command uses per-adapter turn-complete heuristics (e.g., Claude's `stop_reason`, Cursor's last role) rather than polling file modification times, reducing false positives.
- Single-flight concurrency in `watch` ensures only one maintain iteration runs at a time; changes arriving during a run are queued and retried after completion.

## Key Quotes

> "The one command to run after agent sessions land. It runs every stage in order — `sync` → `synth` → `build` → `graph` → `lint`" — clarifies the purpose and orchestration order of the `all` command.

> "`synth` is the only stage that can call an LLM; with the default `dummy` synthesis backend it makes no provider call at all" — establishes that LLM invocation is optional and defaults to no-op.

> "When `--lint-fail` fails the run (exit `2`, unless an earlier step already set a non-zero code), the site HTML from the **preceding build in this run is kept** — lint does not undo or revert `site/`" — documents a key safety property that prevents loss of previously built output.

> "Single-flight: only one maintain iteration at a time (`sync` → `synth` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes." — describes the `watch` command's concurrency model and queue semantics.

## Connections

- [[llmwiki]] (entity) — the project whose CLI this reference documents.
  - fact: The `all` command is the primary workflow entry point for running the full pipeline after agent sessions finish.
- [[Wiki Synthesis]] (concept) — the `synth` stage performs document synthesis via configured backends.
  - fact: Synthesis defaults to a dummy backend making no API calls; real LLM backends are controlled by `--no-synth` and backend configuration.
- [[Static Site]] (entity) — the `build` stage generates the searchable static output.
  - fact: Build artifacts are preserved on disk even when a later `lint` failure occurs in the same run.
- [[Adapters]] (entity) — the `watch` command polls adapter session stores to detect finished sessions.
  - fact: `watch` uses adapter-specific turn-complete signals (e.g., `stop_reason` for Claude, last role for Cursor) rather than file mtime alone, reducing false triggers.
- [[Lint Rules]] (concept) — the `lint` stage validates pages; failure behavior is policy-driven.
  - fact: `--lint-fail` accepts three policies (`never`, `errors`, `warnings`); stricter policies take precedence when both `--lint-fail` and `--strict` are given.
- [[Knowledge Graph]] (concept) — the `graph` stage builds the interconnected knowledge web.
  - fact: `--skip-graph` allows skipping this stage when the graphify engine is unavailable or not installed.

## Contradictions

None identified. The pipeline design, stages, and exit codes align with the project's documented architecture.