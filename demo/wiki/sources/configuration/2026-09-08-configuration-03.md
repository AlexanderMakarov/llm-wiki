---
title: "Configuration (part 3/3: CLI flags)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, cli-flags, sync-quarantine, llmwiki-ignore, static-site-theme]
date: 2026-09-08
source_file: 
project: configuration
model: 
last_updated: 2026-09-08
---
## Summary

Part three of the Configuration doc catalogs **CLI flags** for `sync`, `build`, `init`, and `adapters`, documents **`.llmwikiignore`** (gitignore-style session skips), and summarizes **adapter defaults** for Claude Code, Obsidian, and Codex CLI plus where to change **static site theme** tokens in `llmwiki/build.py`. Sync treats per-file conversion failures as non-fatal by default (quarantine + `--status`); **`--fail-on-errors`** is the hard gate for CI. There is **no** `sync --dry-run` — previews use `add --dry-run` or `sync --status` / `synth --estimate`.

## Key Claims

- By default, a failed per-file conversion during `llmwiki sync` does not abort the run; failures are counted, stored in `llmwiki-state.json` quarantine, and visible via `llmwiki sync --status`, while other files still convert.
- `llmwiki sync --fail-on-errors` exits with code 1 if any file fails to convert, intended for CI and scripted pipelines that must not continue after a partial sync.
- `llmwiki sync` has no `--dry-run`; document intake previews use `add --dry-run`, and sync/synth inspection uses `sync --status` or `synth --estimate`.
- Durable lookback is configured via `filters.since` in `config.json` or `adapters.<name>.since` (date or `"all"`); the CLI `--since YYYY-MM-DD` overrides those for a single run.
- Theme accent colours for the built site are edited in the `CSS` string in `llmwiki/build.py` under the `:root` block (e.g. `--accent`, `--accent-light`, `--accent-bg`); dark-mode variants auto-derive unless overridden.

## Key Quotes

> "Per-file conversion errors do not fail the run by default: each one is counted in the summary, recorded in `llmwiki-state.json` quarantine entries, and visible via `llmwiki sync --status`, while the rest of the corpus still converts."

> "There is **no** `sync --dry-run` — use `add --dry-run` for document intake previews, or inspect with `sync --status` / `synth --estimate`."

## Connections

- [[llmwiki]] (entity) — CLI surface documented here (`sync`, `build`, `init`, `adapters`) and operational behaviour around quarantine and lookback.
  - fact: Sync quarantine and `--status` are the supported way to inspect failed conversions without stopping the whole sync.
- [[Adapters]] (concept) — Named sources selectable with `sync --adapter`, with per-adapter `since` and store overrides in `config.json`.
  - fact: Bare `llmwiki sync` runs all available adapters; `--adapter` limits to named adapter(s).
- [[Claude Code]] (entity) — Default session store `~/.claude/projects/`; overridable in the adapter config block.
- [[Codex CLI]] (entity) — Production core adapter; default roots `~/.codex/sessions` and `~/.codex/projects`; included on bare sync when a root exists.
- [[Obsidian]] (entity) — Optional adapter with default vault path checks and `vault_paths`, `exclude_folders`, `min_content_chars` in config.
- [[Static Site]] (concept) — `llmwiki build --out`, optional `--synthesize` overview via Claude CLI, and theme tokens in `build.py`.
- [[GitHub Actions]] (concept) — `--fail-on-errors` on sync is explicitly aimed at CI pipelines that must not proceed past partial sync failures.
