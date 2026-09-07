---
title: "CLI reference (part 14/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, scheduler-activation, automation-status]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-14.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This segment of the CLI reference documents the status file fields added to `.llmwiki/automation-status.json` when scheduler activation is triggered, including backend type, installation path, activation state, and error tracking.

## Key Claims

- Scheduler activation adds five fields to the automation-status.json file: `scheduler_activated` (boolean), `scheduler_backend`, `scheduler_units_dir`, `scheduler_active`, and `scheduler_error`
- The `scheduler_backend` field stores one of three values: `systemd`, `launchd`, or `schtasks` (platform-specific scheduler implementations)
- The `scheduler_active` field is populated only when the underlying platform provides a read-back mechanism
- The `scheduler_error` field contains a string describing the failure reason when activation fails

## Key Quotes

> "Status file fields (under `<vault>/.llmwiki/automation-status.json`): in addition to job/schedule keys, activation adds `scheduler_activated` (bool), `scheduler_backend` (`systemd` / `launchd` / `schtasks`), `scheduler_units_dir` (install path), `scheduler_active` (read-back when available), and `scheduler_error` (string when activation failed)."

This defines the exact schema of scheduler-related tracking fields in the automation status file, showing how the system captures backend selection and activation success/failure state.

## Connections

- [[Codex CLI]] (product) — This documentation is part of the CLI reference for the Codex command-line tool
  - fact: Scheduler activation status is tracked persistently via structured fields in automation-status.json

## Contradictions

None apparent.