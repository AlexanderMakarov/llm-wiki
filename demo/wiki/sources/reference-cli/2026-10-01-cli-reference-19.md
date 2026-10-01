---
title: "CLI reference (part 19/19: Exit codes (conventions))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, exit-codes, error-handling, synth, command-line]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This page documents the CLI exit code conventions for the llmwiki suite. It establishes standard Unix exit codes (0, 1, 2) and defines special codes for backend usage limits (75) and clean Ctrl+C interruption (130), scoped to the `synth` and `all` commands where applicable.

## Key Claims

- Exit code 0 indicates success
- Exit code 1 indicates operation failure due to a user-visible error
- Exit code 2 indicates usage error (bad flags, missing files, etc.)
- Exit code 75 indicates temporary stop due to backend usage limit reached; retry after reset (specific to `synth` and `all` commands)
- Exit code 130 indicates clean stop after Ctrl+C interruption (specific to `synth` and `all` commands)
- Subcommands document their own non-zero exit conditions where relevant (e.g., `lint --fail-on-errors`)

## Key Quotes

> "Temporary stop: the synthesis backend's usage limit was reached (`synth`, `all`); retry after the reset"

This distinguishes rate-limiting exits from genuine failures, signaling recovery is possible.

## Connections

- [[llmwiki]] (entity) — the CLI tool whose exit code conventions are documented here.
  - fact: Establishes standard exit codes (0, 1, 2, 75, 130) for the tool's command suite.
- [[Codex CLI]] (entity) — referenced in related documentation as the integration point for this CLI from Claude Code.

## Related Documentation

This page is part 19 of a 19-part **CLI reference** series. It cross-references:
- Slash commands (`/wiki-*` surface used from Claude Code)
- UI reference (compiled site screens and navigation)
- Configuration and configuration reference pages