---
title: "CLI reference (part 18/19)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, scheduler-automation, exit-codes, wrapper-scripts, automation-status-file]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documents exit codes and status file structure for the `install-automation` command in [[llmwiki]]. Exit codes distinguish successful installation (0), activation failures (1), and unparseable schedule expressions (2). The status file records scheduler backend type, activation state, and diagnostic information. Wrapper scripts preserve the real exit code of scheduled commands to enable proper error handling and quota enforcement.

## Key Claims

- Exit code 0 indicates successful scheduler file installation or user cancellation at the final confirmation prompt
- Exit code 1 signals scheduler activation failure (the default behavior when `--activate` is used)
- Exit code 2 indicates an unparseable or untranslatable schedule expression
- Wrapper scripts log and exit with the actual scheduled command's exit code, enabling the scheduler to distinguish between soft stops (e.g., `75` for usage limits) and actual failures (e.g., `1`)
- Status file fields include `scheduler_activated` (boolean), `scheduler_backend` (systemd/launchd/schtasks), `scheduler_units_dir`, `scheduler_active`, and `scheduler_error`
- Older wrapper scripts logged `EXIT:0` unconditionally; regenerating them via `install-automation` is required to capture real exit codes

## Key Quotes

> "the scheduled command's real exit code, and exits with that same code — so the scheduler can tell a usage-limit stop (`75`) from a failure (`1`)."
— explains the design rationale for wrapper exit code preservation

> "**Status file fields** (under `<vault>/.llmwiki/automation-status.json`): in addition to job/schedule keys, activation adds `scheduler_activated` (bool), `scheduler_backend` (`systemd` / `launchd` / `schtasks`), `scheduler_units_dir` (install path), `scheduler_active` (read-back when available), and `scheduler_error`"
— comprehensive list of metadata recorded by the automation installer

## Connections

- [[llmwiki]] (entity) — the knowledge base system whose command-line automation interface is being documented
  - fact: Automation installation can target multiple scheduler backends (systemd on Linux, launchd on macOS, schtasks on Windows)