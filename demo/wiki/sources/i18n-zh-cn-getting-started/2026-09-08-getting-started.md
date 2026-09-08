---
title: "快速开始 (Getting started)"
type: source
tags: [wiki-add, raw-doc, session-transcript, i18n-zh-cn-getting-started, setup-script, offline-static-site, session-ingest, llmwiki-setup, vault-scaffold]
date: 2026-09-08
source_file: 
project: i18n-zh-cn-getting-started
model: 
last_updated: 2026-09-08
---
## Summary

This source is the Simplified Chinese (zh-CN) **快速开始** guide for llmwiki, aligned to English `docs/getting-started.md` at v0.3.0 (2026-04-08) as a first-draft translation that may lag the master doc. It walks through a minimal install path: clone the repo, run `setup.sh` or `setup.bat` (idempotent pip + `raw/`/`wiki/`/`site/` scaffold, adapter detection, first-sync dry-run), then use `./sync.sh` and `./build.sh` to populate `raw/sessions/` from agent stores and compile an offline-browsable `site/index.html` with keyboard navigation. Prerequisites are Python ≥3.9, `git`, and existing Claude Code or Codex CLI sessions—no npm, Homebrew, database, or account.

## Key Claims

- A new user can reach a browsable wiki of past agent sessions in about five minutes after clone and setup scripts.
- `setup.sh` / `setup.bat` install only the `markdown` package (highlight.js via CDN at build/view time), create the three-layer vault layout, run `llmwiki adapters`, and preview what the first sync would convert.
- Post-install workflow is two commands: `sync.sh` pulls new sessions into immutable `raw/`, `build.sh` compiles `raw/` + `wiki/` into static `site/` with no server or network required to browse locally.
- macOS is described as shipping Python 3.9+ by default; most Linux distros meet the same floor.
- The zh-CN page explicitly defers authority to the English getting-started doc and marks itself as a v0.3初稿 that may be behind English.

## Key Quotes

> "就这些。无需 `npm`、无需 `brew`、无需数据库、无需账号。" — states the intentional minimal dependency surface for onboarding.

> "站点就是普通文件，无需启动任何服务，也不会请求网络" — defines the static-site model (local files only) after `build.sh`.

> "中文 (简体) 翻译 — 以英文主文档为准" — documents i18n governance: English master is canonical for factual/setup content.

## Connections

- [[llmwiki]] (entity) — product and repo the guide installs and operates (`llmwiki` CLI, `raw/`/`wiki/`/`site/`).
  - fact: Getting started is the entry doc for the Karpathy-style three-layer vault workflow.
- [[Claude Code]] (entity) — primary session source named in prerequisites and the “all sessions you’ve run” outcome.
  - fact: Users need sessions already in the agent default session store before sync is meaningful.
- [[Codex CLI]] (entity) — alternate core agent named alongside Claude Code for session inventory.
- [[Adapters]] (concept) — `llmwiki adapters` and adapter-specific docs linked in “下一步”.
  - fact: Setup includes detecting which agents are available on the machine.
- [[Static Site]] (concept) — `build.sh` output and browser UX (⌘K/Ctrl+K, `/`, `g h`/`g p`/`g s`, `j`/`k`, `?`).
  - fact: Browsing is file-based with no local server.
- [[Obsidian]] (entity) — linked as optional adapter reading path after install.
