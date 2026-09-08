---
title: "CLI reference (part 15/15: Exit codes (conventions))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, exit-codes, cli-conventions, lint-fail-on-errors, usage-errors, llmwiki-cli]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This slice closes the **CLI reference** by documenting **llmwiki**’s shared exit-code conventions: `0` for success, `1` for a user-visible operation failure, and `2` for usage errors (bad flags, missing paths, and similar). It notes that individual subcommands may define additional non-zero exits where behavior matters, with `lint --fail-on-errors` called out as an example. The part also points readers to slash commands, UI reference, and configuration docs.

## Key Claims

- **llmwiki** uses a three-code baseline: `0` success, `1` operation failed (user-visible error), `2` usage error (invalid invocation or missing inputs).
- Subcommands are expected to document their own non-zero exit conditions when those conditions are part of the contract, not only the global table.
- `lint --fail-on-errors` is the documented example of a subcommand-specific non-zero exit path beyond the generic `1`/`2` split.

## Key Quotes

> "`0` | Success" — baseline contract for any successful CLI invocation.

> "`2` | Usage error (bad flags, missing file, etc.)" — distinguishes caller mistakes from operational failures (`1`).

> "Subcommands document their own non-zero exit conditions where relevant (`lint --fail-on-errors`)." — exit semantics are partly global and partly per-command.

## Connections

- [[llmwiki]] (entity) — the CLI whose exit-code table this documents.
  - fact: Documents standardized exit codes `0`/`1`/`2` for the whole tool.
- [[Wiki Synthesis]] (concept) — operators and CI often chain `sync`, `synth`, `lint`, and `build`; predictable exits matter for scripts.
  - fact: Global `1` vs `2` helps automation treat “fix the wiki” differently from “fix the command line.”
- [[GitHub Actions]] (concept) — CI jobs that run `llmwiki lint` or `build` rely on non-zero exits to fail the workflow.
  - fact: `lint --fail-on-errors` is explicitly tied to subcommand-specific failure signaling.
