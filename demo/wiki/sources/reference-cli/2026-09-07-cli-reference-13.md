---
title: "CLI reference (part 13/15: install-automation — set up the daily job)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, daily-automation, cron-scheduling, synthesis-costs]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-13.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This documents the `install-automation` command, which sets up daily scheduled jobs to automate wiki maintenance. The command offers two modes—ingest-only (free) and maintain (with AI provider costs)—and supports interactive or unattended setup via `--yes`. It handles cron scheduling with validation, optional knowledge graph building, and quality checking with configurable failure policies.

## Key Claims

- The `install-automation` command creates daily scheduled jobs to automate wiki updates; ingest-only jobs are free, while maintain jobs send session text to an AI provider and cost money.
- Users can estimate synthesis costs before running the maintain job with `llmwiki synth --estimate`, and the command validates cron expressions against the OS scheduler before writing any unit files.
- The command is interactive by default but fully automatable with the `--yes` flag combined with flags for job mode, schedule, graph builder, and quality failure policies.
- Optional features include knowledge graph building (built-in or richer `graphify` variant) and quality checking with failure policies (on errors, warnings, or never).

## Key Quotes

> "Sets up the job that keeps your wiki current so you do not have to run the steps by hand." — Establishes the core purpose of automation.

> "Sends session text to your AI provider — this costs money once a real provider is configured. Run `llmwiki synth --estimate` to see how much before the job first fires." — Clarifies the cost model for maintain mode and how users can estimate costs upfront.

> "Whatever the route, the schedule is validated before any unit file is written — an expression llmwiki cannot translate into your OS scheduler's own format is refused with the reason." — Demonstrates defensive design in schedule validation.

## Connections

- [[llmwiki]] (system) — the CLI tool being documented; this command automates core wiki maintenance workflows.
  - fact: The command writes automation metadata to `automation-status.json` under the vault and `config.json` at the project level.
  - fact: The maintain job mode invokes synthesis as part of its workflow to summarize sessions and gather topic candidates.
- [[Configuration]] (concept) — the command configures how the daily job runs and persists settings across the system.
  - fact: The `--vault` flag ensures the scheduled job and its status file always refer to the same vault, even if different from `vault.default_path`.
  - fact: The `--synth-backend` flag writes the synthesis backend choice to `config.json` after user confirmation in interactive mode.

## Contradictions

None identified.