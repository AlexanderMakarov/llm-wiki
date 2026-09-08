---
title: "CLI reference (part 11/15: install-agent-kit — copy packaged slash commands and skills (#109))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, install-agent-kit, agent-kit-manifest, cli-provenance, graph-query, slash-commands, provenance-trace]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This slice of the CLI reference documents `install-agent-kit` (copy packaged `/wiki-*` commands and skills into a required `--dest`, upgrade-safe writes with `.bak`, and content-gated pruning of retired kit files via package digests and `.llmwiki-agent-kit.json`), plus `version`, graph-backed `query`, and `trace` for walking wiki provenance from frontmatter to `raw/` without body excerpts.

## Key Claims

- `install-agent-kit` never guesses agent layout: `--dest` is required, and typical targets are project `.claude` or a user-level agent directory.
- On upgrade, matching destination files are left unchanged; differing files get a `.bak` beside the new kit copy, and pruning removes only paths whose bytes still match digests llmwiki previously installed (retired-path list + manifest); user-owned or customised files with unknown hashes are reported as `kept` and not deleted.
- Contributor-only commands and skills (`fix-bug`, `release`, `docs-that-work`, etc.) live in the repo’s `.claude/` tree and are not shipped in the pip/Homebrew kit.
- `query` requires the Graphify extra (`pip install llm-wiki-plus[graph]`) and a prior `llmwiki graph` build; defaults are depth 3 and token budget 2000.
- `trace` resolves a wiki page by path or name under `--vault` (or config default), prints one line per hop (`page` → `source` → `raw`), marks missing hops but still exits 0 unless the start page or vault is unusable (exit 1 or 2).

## Key Quotes

> "`--dest` is **required** — the command does not guess at agent directory conventions." — install scope is explicit so the kit does not assume Claude vs other agent layouts.

> "A file this command never installed is never touched, whatever its name, so your own commands beside the kit's are safe" — pruning is byte-identity gated, not filename gated.

> "Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts." — defines what `trace` is and is not for provenance inspection.

## Connections

- [[llmwiki]] (entity) — documents core CLI subcommands for kit install, version, graph query, and provenance trace.
  - fact: Packaged user kit lives under `llmwiki/agent_kit/` and is copied with `install-agent-kit`.
- [[Claude Code]] (entity) — primary consumer of installed `commands/` and `skills/` under `.claude`.
  - fact: Contributors in the clone run `llmwiki install-agent-kit --dest .claude` for local `/wiki-*` commands.
- [[Knowledge Graph]] (concept) — backing store for `query` after `graph` is built.
  - fact: `query` performs BFS with configurable `--depth` and `--budget`.
- [[Wikilinks]] (concept) — graph and wiki pages are the objects `trace` walks via `sources:` / `source_file:` chains.
  - fact: Broken hops are visible in `trace` output as `(missing)`; repair is manual, `synth`, or `migrate broken-provenance`.
- [[Wiki Synthesis]] (concept) — named alongside synth/migrate when fixing provenance gaps found via `trace` or lint.
