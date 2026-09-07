---
title: "CLI reference (part 1/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, sync-command, adapters, vault-overlay, workflow]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-01.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This documentation provides comprehensive reference for the `llmwiki` CLI, covering all six command groups and the canonical workflow (ingest via `sync`/`add` → synthesize → review → publish). Part 1 documents top-level structure, the idempotent `init` command, the "workhorse" `sync` command with extensive adapter and vault-overlay options, and the `add` command for ingesting external documents. Documentation is validated against the live argparse tree—undocumented flags fail automated guardrail checks.

## Key Claims

1. The `llmwiki` CLI organizes commands into six lifecycle groups: Start here, Daily loop, Run the loop for me, Look around, Take things out, and Rare (one-time)
2. The canonical workflow is: ingest (`sync`/`add`) → synthesize (`synth`) → review candidates → publish (`build`)
3. `synth` does not rebuild the site; `build` must be run separately when Home/Analytics should refresh
4. The `sync` command is the "workhorse" that walks configured adapters, converts sessions to markdown, reconciles `wiki/index.md`, and (by default) auto-builds and auto-lints
5. `sync` supports vault-overlay mode to write new pages to Obsidian/Logseq vaults instead of the repository
6. `init` is idempotent—safe to re-run without overwriting existing files
7. `add` converts URLs, files, or folders into raw markdown documents and batch-synthesizes and rebuilds once per run
8. Documentation serves as a quality gate: "If a command isn't listed here it isn't shipping"

## Key Quotes

> "Every `python3 -m llmwiki <subcommand>` — with every flag, realistic examples, and expected output. If a command isn't listed here it isn't shipping."

Documentation is a guardrail—undocumented features fail automated validation.

> "Canonical loop: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`)."

The primary user workflow, sequencing ingest, synthesis, review, and publication stages.

> "`synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh."

Important architectural clarification: synthesis and site building are separate concerns.

> "The workhorse. Walks every configured adapter, converts new sessions into `raw/sessions/`, reconciles `wiki/index.md` against pages on disk, then (by default) auto-builds and auto-lints."

Central role of `sync` in the daily workflow loop.

## Connections

- [[llmwiki]] (system) — the CLI tool whose interface is documented
  - fact: Defines six command groups organized around ingest/synthesize/publish workflow
  - fact: Documentation is validated against live argparse tree to enforce that all flags are documented before shipping
- [[Adapters]] (concept) — central to the `sync` workflow
  - fact: `sync` walks every configured adapter and converts sessions to raw markdown
  - fact: Adapters support `enabled: false` and can be filtered by name via `--adapter` flag
- [[Obsidian]] (system) — vault integration
  - fact: `sync` and `add` support `--vault PATH` for vault-overlay mode, writing pages to an external Obsidian/Logseq vault instead of the repository
  - fact: Vault mode can append under `## Connections` instead of overwriting with `--allow-overwrite` flag
- [[Wiki Synthesis]] (concept) — part of the canonical workflow
  - fact: `synth` command comes after ingest and before `build` in the workflow
  - fact: `synth` does not rebuild the site; `build` is explicitly separate
- [[Configuration Reference]] (documentation) — configuration flags documented here
  - fact: `sync` supports `--since`, `--project`, `--adapter`, `--force`, `--auto-build`, `--auto-lint` flags
  - fact: `add` supports `--title`, `--project`, `--tag`, `--dry-run`, `--force-new`, `--vault` options