---
title: "CLI reference (part 15/15: Exit codes (conventions))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, exit-codes, unix-conventions]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-15.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This reference page documents standard exit code conventions for the wiki's command-line tools, comprising the final (part 15 of 15) section of the CLI reference documentation. Exit codes follow Unix conventions: 0 for success, 1 for user-visible operation failures, and 2 for usage errors. Subcommand-specific exit codes are documented at the individual command level rather than centrally.

## Key Claims

- The wiki's CLI tools standardize on Unix exit code conventions (0=success, 1=operation failure, 2=usage error)
- Exit code documentation is distributed per-subcommand rather than centralized in the reference
- This documentation completes a comprehensive 15-part CLI reference series

## Key Quotes

> | Code | Meaning |
> |---|---|
> | `0` | Success |
> | `1` | Operation failed (user-visible error) |
> | `2` | Usage error (bad flags, missing file, etc.) |

> Subcommands document their own non-zero exit conditions where relevant

## Connections

- [[Codex CLI]] (tool) — the command-line tool following these exit code conventions
- [[Configuration Reference]] (documentation) — related system reference documentation
- [[llmwiki]] (project) — the wiki system these CLI tools manage