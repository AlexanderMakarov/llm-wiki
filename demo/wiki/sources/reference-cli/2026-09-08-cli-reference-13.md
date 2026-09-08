---
title: "CLI reference (part 13/15: install-automation — set up the daily job)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, install-automation, cron-scheduling, systemd-timers, scheduled-synth, automation-status, wiki-maintenance, synthesis-cost]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents `llmwiki install-automation`, which configures a recurring job so vault ingest, optional AI-backed maintenance (sync → synth → candidates → single site build → lint logged), and optional knowledge-graph builds run on a validated five-field cron schedule. The wizard is interactive by default; `--yes` plus flags supports unattended installs on Linux (systemd user timers with `Persistent=true`), macOS (LaunchAgents), or staged units with `--no-activate`. Automation metadata lands in `<vault>/.llmwiki/automation-status.json` and run output in `last-automation.log`, feeding the site Home Automation panel.

## Key Claims

- **Ingest-only** automation collects new agent sessions into `raw/` and refreshes `site/` without calling an AI provider; **maintain** additionally writes `wiki/sources/` and `wiki/candidates/`, refreshes the browsable site once per cycle after summarization, and records quality-check output in the run log while optionally failing the job via `--lint-fail`.
- Cron schedules must use standard five-field grammar; nicknames, Vixie/Quartz extensions, a seconds field, and expressions that restrict both day-of-month and day-of-week are rejected (exit code `2`) because schedulers cannot express the OR semantics reliably.
- Re-running `install-automation` replaces the existing job rather than registering a second timer; interactive flow defaults to **maintain** on Enter, with **1** selecting ingest-only.
- `--watch-enabled` only sets watch visibility in automation status for the UI—it does not install or start `llmwiki watch`.
- Deprecated `--profile` / `--hour` / `--minute` map to `--job` and `--schedule`, with notices when both old and new flags are present.

## Key Quotes

> "Never contacts an AI provider — free." — Defines the cost boundary between default **ingest** automation and **maintain**, which sends session text to a configured synthesis backend.

> "A separate sync-only path (including optional **Ingest** automation) is a different concern — not 'Maintain finished.'" — Clarifies that ingest automation and the full maintain pipeline are distinct operational models.

> "Stage completion times live under Pipeline state, not Automation." — Separates scheduler/settings UI from per-stage pipeline timing in the product.

## Connections

- [[llmwiki]] (entity) — Host CLI for `install-automation`, vault resolution, and scheduled `sync` / `synth` / `build` / optional graph and lint failure policy.
  - fact: Documented entrypoints include `python3 -m llmwiki install-automation` with `--vault`, `--job`, and `--schedule`.
- [[Wiki Synthesis]] (concept) — **Maintain** job depends on synthesis to populate `wiki/sources/` and harvest `wiki/candidates/`; `--synth-backend` and `llmwiki synth --estimate` tie automation to provider cost.
  - fact: Maintain mode is described as costing money once a real provider is configured.
- [[Static Site]] (concept) — Both job modes refresh `site/`; maintain explicitly builds the site once per cycle after summarization, not on a separate sync-only completion semantics.
- [[Knowledge Graph]] (concept) — Optional `--graph builtin` or `--graph graphify` (extra package) writes `graph/` during maintain runs.
- [[Ollama]] (entity) — Listed as a `--synth-backend` choice alongside `dummy`, `claude`, and `cursor_cli` for automation status and config.
- [[Adapters]] (concept) — Ingest/maintain collection step assumes agent session sources are synced into immutable `raw/` via the adapter stack.
