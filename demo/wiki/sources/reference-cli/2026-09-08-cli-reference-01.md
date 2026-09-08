---
title: "CLI reference (part 1/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cli-reference, sync-command, document-intake, vault-overlay, argparse-guardrails, llmwiki-cli]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the CLI reference maps every shipping `python3 -m llmwiki` subcommand into six lifecycle groups and documents `init`, `sync`, and `add` with flags, examples, and typical output. It states that the page is generated from the live argparse tree so undocumented flags fail CI guardrails, and that the canonical loop is ingest (`sync` / `add`) → `synth` → review candidates → `build`, with `synth` not rebuilding `site/`. `sync` is the adapter-driven path from agent session stores into immutable `raw/sessions/` with default auto-build and auto-lint; `add` ingests URLs, files, or folders into `raw/docs/` with optional dry-run and post-add synthesis.

## Key Claims

- Any command or flag not listed in this reference is not considered shipped; documentation is validated against the live argparse definition.
- `llmwiki sync` defaults to rebuilding `site/` and running `lint` after conversion unless `--no-auto-build` or `--no-auto-lint` is passed.
- There is no `sync --dry-run`; observability uses `sync --status`, and preview for document intake uses `add --dry-run`.
- `llmwiki init` is idempotent and does not overwrite files that already exist when re-run.
- `llmwiki add` converts sources into `raw/docs/`, runs a batch synthesis pass by default (`--no-synthesize` skips it), and rebuilds the site once per run unless `--no-build` is set.
- With `--vault`, sync can write into an Obsidian or Logseq vault; without `--allow-overwrite`, existing vault pages are not clobbered (new material appends under `## Connections` instead).

## Key Quotes

> "If a command isn't listed here it isn't shipping. This page is generated against the live argparse tree, so adding a flag without documenting it will fail the guardrail test." — scope and enforcement of the CLI reference

> "Canonical loop: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`). `synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh." — how daily workflow fits the documented command groups

> "There is no `sync --dry-run`. Use `sync --status` for observability or `add --dry-run` for document-intake previews." — intentional gap between session sync and doc add preview

## Connections

- [[llmwiki]] (entity) — the CLI and package (`llmwiki` / `python3 -m llmwiki`) this reference fully describes
  - fact: Top-level help groups commands into Start here, Daily loop, Run the loop for me, Look around, Take things out, and Rare one-time sections.
- [[Adapters]] (concept) — `sync` walks configured adapters and converts new sessions into `raw/sessions/`
  - fact: `--adapter NAME` limits the run; default is every ingest-ready coding-agent source with a present store and no `enabled: false`.
- [[Wiki Synthesis]] (concept) — follows ingest in the documented loop via `synth`; `add` triggers batch synthesis after intake unless `--no-synthesize`
- [[Static Site]] (concept) — `build` publishes HTML; `sync` and `add` can auto-rebuild `site/` by default
- [[Obsidian]] (entity) — vault-overlay mode (`sync --vault`, `add --vault`) writes into an existing vault instead of repo `wiki/`
- [[Logseq]] (entity) — mentioned alongside Obsidian for vault-overlay sync behavior
- [[Claude Code]] (entity) — example adapter name `claude_code` in `sync --adapter` examples
- [[Codex CLI]] (entity) — example adapter `codex_cli` in multi-adapter sync examples
- [[GitHub Actions]] (concept) — implied by guardrail tests that fail when argparse and docs diverge (CI enforcement referenced in the intro)