---
title: "CLI reference (part 14/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, automation-scheduler, cli-exit-codes, systemd-launchd, vault-config]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

Part 14 of the CLI reference documents exit codes for the automation/scheduler workflow and the extra fields written to `<vault>/.llmwiki/automation-status.json` when scheduler activation runs. Exit `0` means units were written (and activated by default) or the user declined at the final prompt; `1` means activation failed with `scheduler_error` recorded; `2` means the schedule expression cannot be translated by llmwiki.

## Key Claims

- Exit code `0` covers both successful write/activate (unless `--no-activate`) and the case where the user answers **n** at final confirmation, leaving vault and config unchanged.
- Exit code `1` indicates scheduler activation failed when `--activate` is the default; the status file should contain `scheduler_error`.
- Exit code `2` means the schedule is not an expression llmwiki can translate.
- On activation, the status file may include `scheduler_activated`, `scheduler_backend` (`systemd`, `launchd`, or `schtasks`), `scheduler_units_dir`, `scheduler_active` (when read-back is available), and `scheduler_error` on failure.

## Key Quotes

> `0` — the scheduler files were written (and activated unless `--no-activate`), or you answered **n** at the final confirmation (automation skipped; vault and config unchanged).

> `1` — scheduler activation failed (`--activate` default); status file records `scheduler_error`.

## Connections

- [[llmwiki]] (entity) — documents automation CLI behavior and persists scheduler state under `.llmwiki/automation-status.json`.
  - fact: Supports translating schedules into platform schedulers (`systemd`, `launchd`, `schtasks`) with explicit exit codes for skip, activation failure, and untranslatable expressions.
