---
title: "Comenzar (Getting started)"
type: source
tags: [wiki-add, raw-doc, session-transcript, i18n-es-getting-started, i18n, spanish-localization, session-sync, minimal-dependencies, setup-script, sync-build, static-site]
date: 2026-09-08
source_file: 
project: i18n-es-getting-started
model: 
last_updated: 2026-09-08
---
## Summary

This source is the Spanish (`i18n-es`) quick-start for **llmwiki**, aligned to the English master `docs/getting-started.md` at v0.3.0 (marked as draft v0.3, possibly stale). It walks through clone plus `./setup.sh` or `setup.bat`, then `./sync.sh` and `./build.sh`, so a user with existing **Claude Code** or **Codex CLI** sessions can open a navigable static wiki in the browser without npm, Homebrew, a database, or an account.

## Key Claims

- Prerequisites are Python ≥ 3.9, `git`, and at least some agent sessions already in the default session store; no npm, brew, database, or signup is required.
- `setup.sh` / `setup.bat` is idempotent: installs the `markdown` package with `pip install --user`, creates `raw/`, `wiki/`, and `site/`, runs `llmwiki adapters`, and performs a dry-run first sync preview.
- Post-install workflow is `./sync.sh` (agent store → `raw/sessions/<project>/*.md`) then `./build.sh` (`raw/` + `wiki/` → `site/`); the site is ordinary files opened at `site/index.html`.
- Syntax highlighting in the built site uses highlight.js from a CDN, not a local npm toolchain.
- The Spanish page explicitly tracks the English master and warns that the translation may lag behind the master.

## Key Quotes

> "Inicio rápido en 5 minutos. Al terminar tendrás un wiki navegable de cada sesión de Claude Code que hayas ejecutado." — sets the scope and outcome of the guide

> "Eso es todo. Sin `npm`, sin `brew`, sin base de datos, sin cuenta." — states the minimal dependency bar

> "**Borrador v0.3** — esta traducción es una versión inicial y puede estar desactualizada respecto al maestro." — documents translation freshness and authority of the English master

## Connections

- [[llmwiki]] (entity) — the product this getting-started doc installs and runs
  - fact: Two-command loop after setup is sync then build to produce a browsable wiki.
- [[Claude Code]] (entity) — primary agent whose saved sessions feed `raw/` via sync
  - fact: Quick start assumes sessions already exist in the agent’s default store.
- [[Codex CLI]] (entity) — alternate core agent named alongside Claude Code for session prerequisites
  - fact: Either agent’s sessions satisfy the “some sessions already saved” requirement.
- [[Static Site]] (concept) — output of `build.sh` as local HTML with keyboard navigation
  - fact: No server required; shortcuts include ⌘K/Ctrl+K, `/`, `g h` / `g p` / `g s`, `j`/`k`, and `?`.
- [[Adapters]] (concept) — setup runs `llmwiki adapters` to show which agents were detected
  - fact: Adapter discovery is part of first-run setup before the user syncs.
- [[Obsidian]] (entity) — linked as a follow-on adapter doc from “Siguientes pasos”
  - fact: Getting started points readers to the Obsidian adapter page after install, not as a install prerequisite.