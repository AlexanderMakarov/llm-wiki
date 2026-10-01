---
title: "CLI reference (part 16/19: all — run the full pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, all-command, watch-polling, pipeline-orchestration, lint-policy, exit-codes]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This is a CLI reference documenting two core llmwiki commands: `all`, which orchestrates the full wiki pipeline (sync → synth → build → graph → lint) in one operation, and `watch`, which polls adapter stores for session completion and triggers maintenance near-real-time. The documentation specifies fine-grained exit codes, flag conflict resolution, and the lint failure policy that determines when lint findings block the run.

## Key Claims

- The `all` command is the standard entry point after agent sessions land, running every stage in order with opt-out flags for each
- Only the `synth` stage can call an LLM; the dummy backend makes no provider calls by default, and `--no-synth` skips LLM calls entirely
- Lint findings are always printed; the `--lint-fail` policy (never/errors/warnings) determines whether they fail the run, not whether they are reported
- The `watch` command uses per-adapter turn-complete heuristics (e.g., Claude `stop_reason`, Cursor last role) to detect session completion without waiting for a multi-minute mtime quiesce
- Exit codes distinguish failure modes: `0` (success), `1` (stage failure), `2` (lint policy met or missing directory), `75` (synth usage limit), `130` (Ctrl+C interrupt)
- When conflicting flags are given (e.g., `--no-synth` and `--with-synth`), opt-out flags always win; strict lint policies take precedence over lenient ones

## Key Quotes

> "The one command to run after agent sessions land. It runs every stage in order — `sync` → `synth` → `build` → `graph` → `lint` — so a scheduled job is a bare `llmwiki all` rather than a trail of flags."

This establishes `all` as the canonical orchestration verb for CI/CD and scheduled jobs.

> "Polls adapter session stores on an interval and runs maintain when a session looks finished. Uses per-adapter turn-complete heuristics (Claude `stop_reason`, Cursor last role, Codex events)."

Shows how `watch` avoids long settling delays by using adapter-specific completion signals rather than uniform mtime thresholds.

> "`lint` always prints its findings. `--lint-fail` decides whether those findings end the run"

Clarifies the decoupling: lint issues surface unconditionally, but exit code 2 is only set if the failure policy is met.

## Connections

- [[llmwiki]] (entity) — commands being documented as part of the main CLI interface
  - fact: `all` is the standard pipeline entry point; `watch` enables continuous maintenance mode

- [[Wiki Synthesis]] (concept) — `synth` is the only LLM-calling stage in the pipeline
  - fact: default `dummy` backend makes no provider calls; `--no-synth` skips it entirely

- [[Lint Rules]] (concept) — lint failure policy and exit code semantics
  - fact: `--lint-fail {never,errors,warnings}` controls whether lint findings fail the run

- [[GitHub Actions]] (entity) — use context for CI/CD integration
  - fact: `--fail-fast`, `--lint-fail warnings` / `--strict`, and exit codes support unattended automation

## Contradictions

None identified.