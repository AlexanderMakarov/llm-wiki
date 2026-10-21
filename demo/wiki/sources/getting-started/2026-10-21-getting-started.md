---
title: "Getting started"
type: source
tags: [wiki-add, raw-doc, getting-started, llmwiki-docs, installation, vault-setup, shell-completion]
date: 2026-10-21
source_file: raw/docs/getting-started/getting-started.md
project: getting-started
model: 
last_updated: 2026-10-21
---
## Summary

This source is the getting-started guide for llmwiki, a tool that builds a browsable wiki from coding-agent session transcripts. It walks through prerequisites (Python 3.12+, git), cloning the code repo, and separating code from personal data by creating an external vault pointed to by a gitignored `config.json`. It also covers the core commands (`sync`, `synth`, `build`, `all`), optional adding of non-session documents, automation via `install-automation`, and optional auto-sync via a Claude Code SessionStart hook.

## Key Claims

- llmwiki requires Python ≥ 3.12 and git; no npm, brew, database, or account is needed.
- The git clone contains only code and demo seeds; transcripts, wiki pages, and the built site live in a vault directory outside the repo.
- Setting `vault.default_path` in `config.json` makes `sync`, `build`, `synth`, `queue`, `lint`, and `init` target the vault without a `--vault` flag.
- A bare `llmwiki sync` processes every enabled coding-agent source whose store exists on disk; `--adapter <name>` limits a run to one source.
- `setup.sh` / `setup.bat` is idempotent, installs the `markdown` dependency via `pip install --user`, and reports detected agents and sync status.
- Syntax highlighting is done in the browser via highlight.js, so the build remains stdlib-only.
- `llmwiki add` writes raw documents to `<vault>/raw/docs/` and does not synthesize wiki source pages unless `--synthesize` is passed.
- `llmwiki install-automation` sets up a daily job; collect-only mode never contacts an AI provider, while summarising does.
- Building wiki pages (Karpathy layer 2) requires an LLM agent, e.g. `/wiki-ingest` run inside Claude Code.

## Key Quotes

> "No `npm`, no `brew`, no database, no account." — stating the install's minimal dependency footprint.

> "The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo." — the core separation of code from personal data.

> "`setup.sh` / `setup.bat` is idempotent and…" — setup is safe to re-run.

## Connections

- [[llmwiki]] (entity) — the CLI and knowledge-base builder this guide installs and configures
  - fact: Commands `sync`, `synth`, `build`, `all`, `add`, `install-automation` form the day-to-day workflow.
- [[Adapters]] (concept) — session-store integrations that `sync` reads from
  - fact: `llmwiki adapters` lists detected agent stores; `configure-sources` writes `adapters.<name>` settings.
- [[Claude Code]] (entity) — agent used both as a session source and for running `/wiki-ingest`
  - fact: A `SessionStart` hook in `~/.claude/settings.json` can run sync automatically when Claude Code starts.
- [[Obsidian]] (entity) — the guide links an Obsidian vault as an additional source
  - fact: `adapters/obsidian.md` documents using an Obsidian vault as an extra source.
- [[Wiki Synthesis]] (concept) — the `synth` step and `/wiki-ingest` workflow that produce wiki pages from raw sources
  - fact: `llmwiki synth` fills `wiki/sources/` and harvests `wiki/candidates/` for review.
- [[Static Site]] (concept) — the HTML output produced by `llmwiki build`
  - fact: `build` compiles `<vault>/raw/` and `<vault>/wiki/` into `<vault>/site/`, viewable as plain files.
- [[Frontmatter]] (concept) — metadata block pages carry, referenced in the vault layout
  - fact: Wiki pages are plain markdown files stored in the vault's `wiki/` directory.

## Contradictions

None identified.