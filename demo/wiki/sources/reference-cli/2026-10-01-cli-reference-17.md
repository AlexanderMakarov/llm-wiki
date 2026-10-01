---
title: "CLI reference (part 17/19: install-automation — set up the daily job)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, automation, scheduling, cron, daily-jobs]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Documents the `install-automation` command, which configures recurring automation jobs to keep a wiki current without manual intervention. Two job modes are available: "Ingest only" (default, free) collects sessions and refreshes the site; "Maintain" additionally synthesizes pages and checks quality (requires an AI provider). The command supports interactive or unattended setup with cron-based scheduling, optional graph building, and quality failure policies, with validation before any system changes occur.

## Key Claims

- The default automation job is "Ingest only," which never contacts an AI provider and incurs no cost
- The "Maintain" automation job synthesizes sessions into wiki pages and performs quality checks, requiring an AI provider configuration and incurring synthesis costs
- The install-automation command validates cron expressions before creating scheduler unit files and rejects invalid expressions with a specific error message (exit code 2)
- Automation status and configuration persist in `.llmwiki/automation-status.json` under the vault, enabling independent status tracking for the Home Automation UI
- Synthesis backends (dummy, ollama, claude, cursor_cli) are configurable during setup and stored in config.json for use across automation jobs

## Key Quotes

> "Collects new agent sessions into your vault and refreshes the site… Never contacts an AI provider — free." — describes the default "Ingest only" job mode, emphasizing its cost-free operation.

> "Sends session text to your AI provider — this costs money once a real provider is configured. Run `llmwiki synth --estimate` to see how much before the job first fires." — documents the cost model for "Maintain" jobs and provides a way to estimate expenses before activation.

> "An expression llmwiki cannot translate into your OS scheduler's own format is refused with the reason (exit code `2`)." — ensures scheduling expressions are validated before modifying system scheduler configuration.

## Connections

- [[llmwiki]] (entity) — core system whose automation infrastructure this command configures
  - fact: Configuration and status are stored vault-locally in config.json and `.llmwiki/automation-status.json` to persist across restarts

- [[Wiki Synthesis]] (concept) — the "Maintain" job mode performs synthesis to turn sessions into wiki pages
  - fact: Synthesis backend is configurable via `--synth-backend` with options including dummy, ollama, claude, and cursor_cli

- [[Lint Rules]] (concept) — optional quality checking integrated into the job
  - fact: Quality findings can be configured to fail the job on errors or warnings via the `--lint-fail` flag

- [[Observability]] (concept) — logging and monitoring of automated job execution
  - fact: Each job run appends to `<vault>/.llmwiki/last-automation.log`, which is truncated at the start of each new run

- [[Knowledge Graph]] (concept) — optional graph building as part of the maintenance job
  - fact: Graph building can be enabled via `--graph builtin` or `--graph graphify` (the latter requires `pip install llm-wiki-plus[graph]`)

## Contradictions

None identified.