---
title: "CLI reference (part 1/19)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, sync-command, vault-overlay, initialization, observability]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This document (part 1 of 19) establishes the [[llmwiki]] CLI reference, documenting the canonical workflow loop (ingest → synthesise → review → publish) and providing detailed coverage of the `init` and `sync` commands with all flags, examples, and expected outputs. The `sync` command is identified as the workhorse for converting sessions from configured [[Adapters]] into the wiki, and vault-overlay mode is introduced as a capability to write directly to external [[Obsidian]] or Logseq vaults instead of the default `wiki/` directory. The document emphasizes that CLI documentation is auto-generated against the live argparse tree and guardrailed—adding flags without documenting them will fail validation.

## Key Claims

- The canonical workflow is: ingest (`sync` / `add`) → synthesise (`synth`) → review candidates → publish (`build`), with `synth` not rebuilding the site (requires separate `build`).
- `sync` is the workhorse: walks every configured adapter, converts sessions into `raw/sessions/`, reconciles `wiki/index.md`, and optionally auto-builds and auto-lints by default.
- CLI documentation is generated against the live argparse tree; adding a flag without documenting it fails the guardrail test.
- Vault-overlay mode writes new pages directly to external [[Obsidian]] or Logseq vaults via `--vault` flag instead of to the default `wiki/` directory.
- There is no `sync --dry-run`; `--status` provides observability (last-sync time, per-adapter counters, quarantine) without executing a sync.
- The `init` command is idempotent and safely scaffolds `raw/`, `wiki/`, and `site/` directories plus nine navigation files.

## Key Quotes

> "Every `python3 -m llmwiki <subcommand>` — with every flag, realistic examples, and expected output. If a command isn't listed here it isn't shipping. This page is generated against the live argparse tree, so adding a flag without documenting it will fail the guardrail test."
> — Establishes the contract that CLI documentation is auto-validated against the live interface.

> "Canonical loop: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`). `synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh."
> — Defines the workflow principle underlying all CLI commands.

> "`sync` is the workhorse. Walks every configured adapter, converts new sessions into `raw/sessions/`, reconciles `wiki/index.md` against pages on disk, then (by default) auto-builds and auto-lints."
> — Identifies sync's central role in the ingest phase.

## Connections

- [[llmwiki]] (entity) — The command-line system documented here; all commands are part of its interface.
  - fact: Uses six lifecycle command groups (Start here, Daily loop, Run the loop, Look around, Take out, Rare).
  - fact: CLI is generated from live argparse tree with guardrail validation.

- [[Adapters]] (concept) — Pluggable content sources (claude_code, codex_cli, notes) that `sync` ingests from via `--adapter` flag.
  - fact: `sync --adapter NAME [NAME ...]` limits ingest to specific adapters; defaults to all ingest-ready sources.

- [[Obsidian]] (entity) — External note-taking application supported via vault-overlay mode.
  - fact: `sync --vault PATH` writes new pages into external vault instead of default `wiki/` directory.

- [[Wiki Synthesis]] (concept) — The lifecycle pattern: sync (ingest) → synth (summarize) → candidates (review) → build (publish).
  - fact: `synth` does not rebuild the site; `build` must be run separately for publication.

- [[Lint Rules]] (concept) — Validates CLI documentation against live argparse tree as a guardrail.
  - fact: Missing documentation for new flags causes lint failure.

- [[Observability]] (concept) — `--status` flag provides non-destructive observability without running sync.
  - fact: `--status` shows last-sync time, per-adapter session counters, and quarantine list; `--recent N` adds log entries.