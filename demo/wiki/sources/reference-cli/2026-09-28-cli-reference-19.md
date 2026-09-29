---
title: "CLI reference (part 19/19: Exit codes (conventions))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, exit-codes, error-handling, usage-limits]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

Documents standardized exit codes (0, 1, 2, 75, 130) for the llmwiki command-line interface, combining POSIX conventions with domain-specific codes for backend resource exhaustion and clean interruption. Exit code 75 specifically signals when the synthesis backend's usage limit is reached, enabling clients to implement retry logic after the reset period.

## Key Claims

- Exit code 0 indicates success; 1 indicates a user-visible operation error; 2 indicates a usage/syntax error
- Exit code 75 signals that the synthesis backend's usage limit was reached on `synth` and `all` subcommands; clients should retry after the reset period
- Exit code 130 indicates the program was cleanly interrupted by Ctrl+C
- Subcommands document their own non-zero exit conditions where relevant (e.g., `lint --fail-on-errors`)

## Key Quotes

> "Temporary stop: the synthesis backend's usage limit was reached (`synth`, `all`); retry after the reset"

This documents how resource constraints in the synthesis subsystem are communicated to enable proper backoff and retry strategies in automated workflows.

## Connections

- [[llmwiki]] (entity) — the system whose CLI is documented in this reference
  - fact: Exit code 75 and 130 are specific to `synth` and `all` subcommands for synthesis operations
- [[Wiki Synthesis]] (concept) — the specific operations referenced in exit codes 75 and 130
  - fact: Exit code 75 indicates the synthesis backend reached its usage limit; retry after reset is required