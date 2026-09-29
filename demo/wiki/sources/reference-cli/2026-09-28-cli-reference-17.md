---
title: "CLI reference (part 17/19: install-automation — set up the daily job)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, automation, scheduling, daily-job]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

The `install-automation` CLI command sets up operating-system-scheduled jobs that keep an LLM wiki current without manual intervention. It offers two job profiles: ingest-only (free, collects sessions and refreshes the site) and maintain (AI-powered synthesis at provider cost). Both can optionally build knowledge graphs and configure quality check policies. The command runs interactively by default, showing the exact command line before writing scheduler unit files; it accepts a `--yes` flag for unattended installation. Jobs are installed into systemd (Linux) or LaunchAgents (macOS) with optional catch-up on resume via `Persistent=true`.

## Key Claims

- Ingest-only jobs collect agent sessions and refresh the site without contacting an AI provider and thus cost nothing; maintain jobs include synthesis and cost money based on provider usage.
- The `install-automation` command validates cron expressions before writing unit files; invalid expressions are rejected with exit code 2 and a reason message.
- On Linux, systemd timers with `Persistent=true` enable catch-up of missed runs once after wake, rather than running repeatedly for each skipped day while the system was offline.
- Optional quality checks can be configured to fail the job on errors only, warnings and errors, or never; without a failure policy the quality check still runs but does not mark the job as failed.
- Re-running `install-automation` replaces the existing job rather than adding a second one; it supports both interactive and unattended (`--yes`) modes.

## Key Quotes

> "Sets up the job that keeps your wiki current so you do not have to run the steps by hand. Interactive by default: it asks what the daily job should do, when it should run, and shows you the exact command line before writing anything." — The purpose and interactive workflow of the command.

> "Whatever the route, the schedule is validated before any unit file is written — an expression llmwiki cannot translate into your OS scheduler's own format is refused with the reason (exit code `2`)." — Cron validation happens before any system changes are made.

> "A separate sync-only path (including optional **Ingest** automation) is a different concern — not 'Maintain finished.'" — Clarifies that ingest automation runs independently of the maintain/synthesis workflow.

## Connections

- [[llmwiki]] (entity) — the CLI tool documented; install-automation is one of its commands for setting up daily automation.
  - fact: The command sets up operating-system-scheduled jobs to keep wikis current without manual intervention.
- [[Wiki Synthesis]] (concept) — the maintain job profile includes AI-powered synthesis to convert sessions into wiki pages.
  - fact: Maintain jobs summarize each session into a wiki page and gather candidate topics for review.
- [[Static Site]] (entity) — both ingest-only and maintain jobs refresh the browsable site.
  - fact: The ingest-only job "collects new agent sessions into your vault and refreshes the site."
- [[Lint Rules]] (concept) — quality checks can be configured to fail the job conditionally via --lint-fail flags.
  - fact: Optional --lint-fail policies allow the job to fail on errors, warnings, or never (default).
- [[Knowledge Graph]] (concept) — optional feature in maintain mode; the job can build the graph with --graph builtin or --graph graphify.
  - fact: Graph building is an optional extra offered during wizard configuration; fallback to built-in builder until graphify extra is installed.
- [[Ollama]] (entity) — mentioned as a synthesis backend option for the --synth-backend flag in unattended installation.
  - fact: The --synth-backend flag accepts dummy, ollama, claude, or cursor_cli to set the synthesis provider.