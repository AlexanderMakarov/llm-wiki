---
title: "はじめに (Getting started)"
type: source
tags: [wiki-add, raw-doc, session-transcript, i18n-ja-getting-started, installation, quickstart, session-sync, i18n, setup-scripts]
date: 2026-09-08
source_file: 
project: i18n-ja-getting-started
model: 
last_updated: 2026-09-08
---
## Summary

This source is the Japanese **はじめに (Getting started)** doc: a five-minute quickstart for [[llmwiki]] that treats English [`docs/getting-started.md`](../../getting-started.md) as canonical and marks the JA copy as a **v0.3 draft** that may lag the English master (last synced v0.3.0, 2026-04-08). It walks through clone + `./setup.sh` or `setup.bat`, then `./sync.sh` and `./build.sh`, so [[Claude Code]] or [[Codex CLI]] sessions in the default agent store become a browsable wiki under `site/`. Prerequisites are Python ≥3.9 and `git` only—no npm, Homebrew, database, or account.

## Key Claims

- The English getting-started page is the authoritative source; the Japanese file is an initial translation and may be behind the latest English version.
- `setup.sh` / `setup.bat` run idempotently: user-level `pip install` for the required `markdown` package, scaffold `raw/`, `wiki/`, `site/`, run `llmwiki adapters` to list detected agents, and dry-run the first sync to preview conversions.
- Post-install workflow is two scripts: `sync.sh` pulls new sessions from agent stores into `raw/sessions/<project>/*.md`, and `build.sh` compiles `raw/` + `wiki/` into `site/` with syntax highlighting via CDN highlight.js (no local npm stack).
- Opening `site/index.html` is sufficient—static files only—with documented shortcuts (⌘K/Ctrl+K palette, `/` search, `g h` / `g p` / `g s`, `j`/`k` table nav, `?` help).

## Key Quotes

> "5 分間のクイックスタート。終われば、実行したすべての Claude Code セッションが閲覧可能な Wiki として手に入ります。" — States the doc’s promise: minimal time to a session-backed wiki (Claude Code called out explicitly in JA copy).

> "これだけです。`npm` も `brew` もデータベースもアカウントも不要です。" — Positions llmwiki’s default install as stdlib + git + existing agent sessions, not a full JS or cloud toolchain.

## Connections

- [[llmwiki]] (entity) — Product and repo this page onboard users to (clone, setup, sync, build).
  - fact: Default quickstart uses `./setup.sh`, `./sync.sh`, and `./build.sh` with no extra package managers beyond pip for `markdown`.
- [[Claude Code]] (entity) — Named as a supported session source alongside Codex in prerequisites and in the quickstart tagline.
  - fact: Users need sessions already in the agent’s default session store before sync is meaningful.
- [[Codex CLI]] (entity) — Listed with Claude Code as an acceptable existing session source for the quickstart.
- [[Adapters]] (concept) — `llmwiki adapters` is part of setup to show which agents were detected.
  - fact: Setup includes running adapters discovery before the first sync dry-run.
- [[Static Site]] (concept) — `build.sh` produces `site/`; the page describes keyboard navigation on the generated HTML and points to architecture, configuration, and privacy docs next.
- [[Obsidian]] (entity) — Linked under “次のステップ” as the Obsidian adapter doc, not required for the minimal quickstart path.