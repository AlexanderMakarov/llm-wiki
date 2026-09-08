---
title: "CLI reference (part 2/15: remove — cascade-remove a raw doc and everything derived (#B2))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, cascade-remove, cli-remove, static-site-build, search-index, vault-overlay, cascade-deletion, synth-state]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents two llmwiki CLI commands: **`remove`**, which cascade-deletes matching `raw/docs/` entries together with derived `synth.files` keys and `wiki/sources/` pages (including part-pages), then prunes backlinks, rebuilds `wiki/index.md`, and logs the operation; and **`build`**, which compiles `wiki/` into static HTML under `site/` while emitting bundled AI-oriented exports (`llms.txt`, sitemap, RSS, graph JSON-LD, etc.) without a separate `export` subcommand. Safety rules for `remove` include mandatory `--yes` on non-TTY stdin and optional `--dry-run` for full cascade preview.

## Key Claims

- `llmwiki remove SELECTOR` matches project names or slug globs under `raw/docs/` and deletes raw files plus every derived artifact (synth state keys and corresponding `wiki/sources/` pages) so naive manual deletes cannot leave orphan wiki pages or dangling synthesis state.
- Without both `--dry-run` and `--yes`, `remove` prints the cascade and prompts on a TTY; with no TTY it exits with code 2 rather than performing silent cascade deletion.
- A selector that matches nothing is a clean no-op with a message, not an error.
- `llmwiki build` is the sole step that turns wiki markdown into `site/` HTML and writes the listed AI-consumable exports into the output directory—there is no standalone `export` subcommand.
- By default, `build` does not mutate `wiki/`; `--seed-project-stubs` optionally creates missing `wiki/projects/<slug>.md` stubs (#414).

## Key Quotes

> "Selects raw docs under the resolved vault's `raw/docs/` by a project name or slug glob, then removes them **together with** every artifact derived from them — the `synth.files` state keys and the `wiki/sources/` pages (part-pages included) — so a naive delete can never leave orphan pages or dangling state behind." — Defines the #B2 cascade contract for `remove`.

> "**Required** when stdin is not a TTY — cascade deletion is never silent." — Non-interactive safety for `remove`.

> "Also writes AI-consumable exports … into the output directory — there is no separate `export` subcommand." — Bundled export behavior on `build`.

## Connections

- [[llmwiki]] (entity) — Host toolchain whose CLI implements vault-scoped `remove` and `build`.
  - fact: `remove` reconciles `wiki/index.md` and appends a `remove` entry to `wiki/log.md` after cascade deletion.
- [[Static Site]] (concept) — `build` compiles `wiki/` markdown into `site/` HTML plus search index chunks and optional `graph.html`.
  - fact: Expected build output includes search-index metadata, seven AI exports, interactive graph viewer, and a file count summary line.
- [[Wiki Synthesis]] (concept) — Derived work is tracked in `synth.files` state keys that `remove` deletes alongside source pages.
  - fact: Cascade removal explicitly targets state keys tied to removed raw docs, not just filesystem paths under `wiki/sources/`.
- [[Wikilinks]] (concept) — Post-removal backlink pruning keeps the link graph consistent after pages disappear.
  - fact: `remove` prunes backlinks after deleting derived wiki pages.
- [[Obsidian]] (entity) — Vault-overlay builds can target an existing Obsidian (or Logseq) vault via `--vault` while still writing HTML to `--out`.
  - fact: `--vault PATH` builds from an external vault layout; output directory remains controlled by `--out`.
