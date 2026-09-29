---
title: "CLI reference (part 1/19)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, sync-command, vault-overlay, adapter-configuration, canonical-workflow]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This is comprehensive reference documentation for the [[llmwiki]] CLI, covering top-level commands and the first major subcommands (`init`, `sync`). It documents the canonical workflow—ingest (sync/add) → synthesize (synth) → review → publish (build)—and clarifies that `synth` does not rebuild the site. Commands are organized into six lifecycle sections, and the documentation emphasizes that this page is generated against the live argparse tree.

## Key Claims

- The canonical workflow is: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`)
- `synth` does not rebuild the site; `build` must be run afterwards for Home / Analytics to refresh
- `sync` is idempotent and safe to re-run; it never overwrites existing files
- `init` creates three data directories (raw/, wiki/, site/) and seeds nine navigation files
- There is no `sync --dry-run`; use `sync --status` or `add --dry-run` instead
- Commands are grouped into six lifecycle sections in help output: Start here, Daily loop, Run the loop for me, Look around, Take things out, and Rare
- `sync` is described as "the workhorse" that walks configured adapters and converts sessions to markdown

## Key Quotes

> "Canonical loop: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`). `synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh."
— establishes the core workflow and corrects a common misconception about synth's responsibilities

> "`sync` is the workhorse."
— identifies sync as the primary ingest command

> "Idempotent. Safe to re-run — it never overwrites files that exist."
— guarantees safety of `init` repeated invocations

## Connections

- [[llmwiki]] (entity) — the CLI tool being comprehensively documented with every subcommand, flag, and example
  - fact: Commands are grouped into six lifecycle sections accessible via `llmwiki --help`
  - fact: TAB completion for command names is available in bash and zsh
  
- [[Adapters]] (entity) — loaded and processed via the `sync --adapter NAME` flag
  - fact: Default loads every ingest-ready source with a present store and no `enabled: false`
  - fact: Notes intake requires `enabled: true` in adapter configuration
  
- [[Obsidian]] (entity) — supported as vault target for overlay mode
  - fact: `sync --vault "path"` writes new pages into an existing Obsidian vault
  - fact: `--allow-overwrite` clobbering is disabled by default; pages are instead appended under `## Connections`
  
- [[Logseq]] (entity) — mentioned as alternative vault system for overlay mode
  - fact: Works with same `--vault` flag as Obsidian vaults