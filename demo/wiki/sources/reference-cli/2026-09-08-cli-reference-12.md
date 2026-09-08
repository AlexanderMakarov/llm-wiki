---
title: "CLI reference (part 12/15: all — run the full pipeline)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, pipeline-orchestration, watch-mode, lint-fail-policy, fail-fast, scheduled-jobs, llmwiki-all, scheduled-maintenance]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents `llmwiki all` as the single entry point that runs the full maintain pipeline in order (`sync` → `synth` → `build` → `graph` → `lint`), with per-stage opt-outs and a configurable lint failure policy for CI. It also documents `llmwiki watch`, which polls agent session stores on an interval and runs a default maintain subset (`sync` → `synth` → `build`) under single-flight semantics with dirty retries when changes arrive mid-run.

## Key Claims

- `llmwiki all` is intended as the one scheduled command after sessions land; AI-facing exports such as `llms.txt` and `sitemap.xml` are produced by `build`, not as a separate step.
- Only `synth` can invoke an LLM; with the default `dummy` synthesis backend it makes no provider call, and `--no-synth` disables synthesis entirely.
- By default, `all` continues later stages after a non-zero step (e.g. build still runs if synth fails after a successful sync) and reports the worst exit code; `--fail-fast` stops at the first failing step.
- `--lint-fail never` (default) always exits `0` after printing lint findings; `errors` or `warnings` can exit `2` while leaving `site/` HTML from the preceding build in the same run unchanged.
- `watch` uses per-adapter “session finished” heuristics (e.g. Claude `stop_reason`, Cursor last role, Codex events); adapters without a finished signal use a short mtime settle (default 2s), not a long quiesce.
- Only one maintain iteration runs at a time in `watch`; concurrent changes set a dirty flag and trigger a retry after the current run finishes; sync may time out (~180s) while synth and build have no timeout.

## Key Quotes

> "The one command to run after agent sessions land."

> "When `--lint-fail` ends the run with exit `2`, the site HTML from the **preceding build in this run is kept** — lint does not undo or revert `site/`."

> "Single-flight: only one maintain iteration at a time (`sync` → `synth` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes."

## Connections

- [[llmwiki]] (entity) — CLI orchestration for vault maintain: `all` runs the full pipeline; `watch` polls and maintains on session completion.
  - fact: Default pipeline order for `all` is sync → synth → build → graph → lint, each skippable via dedicated flags.
- [[Wiki Synthesis]] (concept) — The synth stage is the only pipeline step that may call an LLM; `--no-synth` and the default dummy backend avoid provider calls.
- [[Static Site]] (concept) — `build` writes `site/` and bundled exports; lint failure does not revert a successful build in the same `all` run.
- [[Knowledge Graph]] (concept) — `graph` is a stage in `all`, with `--graph-engine {builtin,graphify}` and `--skip-graph` when graphify is unavailable.
- [[Adapters]] (concept) — `watch` polls ingest-ready coding-agent stores and respects per-adapter finished-session signals.
- [[Claude Code]] (entity) — Named as a watch target via `--adapter` and as a source of turn-complete heuristics (`stop_reason`).
- [[Cursor]] (entity) — Listed among adapters for `watch`; completion inferred from last role in the chat store.
- [[Codex CLI]] (entity) — Listed among adapters; completion inferred from Codex session events.
- [[GitHub Actions]] (concept) — Example use: `llmwiki all --skip-graph --lint-fail warnings` to fail CI on any lint issue while skipping optional graphify.
