---
title: "Setup Guide — Your First LLM Wiki in 15 Minutes (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-setup-guide, github-pages, vault-layout, first-sync, session-adapters, getting-started, static-site, session-sync, adapter-detection]
date: 2026-09-08
source_file: 
project: tutorials-setup-guide
model: 
last_updated: 2026-09-08
---
## Summary

Part 1 of the “15 minutes” setup guide walks through cloning **llm-wiki**, running `setup.sh` / `setup.bat`, and the first `llmwiki sync` and `llmwiki build`. The script scaffolds the Karpathy three-layer layout (`raw/`, `wiki/`, `site/`), installs **llmwiki** editable, probes common agent and Obsidian paths for **Adapters**, optionally wires a Claude **SessionStart** auto-sync hook, and runs an initial sync. The doc then explains what session, project, and home pages show in the built **Static Site**, and how **GitHub Pages** deploys only the committed `demo/` vault via **GitHub Actions** while personal `raw/` and `wiki/` stay local and gitignored.

## Key Claims

- Prerequisites for the tutorial are Python 3.12+ and git only—no Node, Docker, or database.
- `setup.sh` / `setup.bat` create the three-layer directory structure, `pip install -e .`, detect coding agents and vault paths, optionally install a Claude SessionStart sync hook, and run a first sync.
- In `llmwiki sync` summary output, `live` means the session was active in the last 60 minutes and is skipped for safety.
- Raw session files land under `raw/sessions/` as `YYYY-MM-DDTHH-MM-project-slug.md` (flat naming).
- `llmwiki build` emits plain HTML under `site/` plus `search-index.json` and chunked search assets; opening `site/index.html` requires no server.
- The public **GitHub Pages** workflow builds with `llmwiki build --vault demo --out ./site` on push to `master`, so the published site uses demo data, not the operator’s personal sessions.
- Personal `raw/` and `wiki/` are gitignored by default; only demo/screenshot-style content is intended for the public repo deploy.

## Key Quotes

> "The public deploy uses demo data, NOT your personal sessions. Your actual `raw/` and `wiki/` folders are gitignored by default."

> "Creates the 3-layer directory structure per Karpathy's LLM Wiki pattern: `raw/` — immutable session transcripts (Layer 1); `wiki/` — LLM-maintained pages (Layer 2); `site/` — generated HTML (Layer 3)"

## Connections

- [[llmwiki]] (entity) — End-to-end product the tutorial installs and operates (`sync`, `build`, vault layout).
  - fact: Setup script installs the package editable and runs first sync/build as the happy path.
- [[Static Site]] (concept) — Layer 3 HTML, search index, and offline `site/index.html` browsing.
  - fact: Build discovers sources across projects and writes session/project pages plus search chunks.
- [[Adapters]] (concept) — Pluggable sources for Claude Code, Codex CLI, Cursor, Gemini, Copilot, Obsidian paths.
  - fact: Setup detects agent stores and reports which adapters are ready vs need path configuration.
- [[GitHub Pages]] (concept) — Optional public URL at `https://<user>.github.io/<repo>/`.
  - fact: Enabled with Pages source “GitHub Actions”; first deploy often takes 30–60 seconds.
- [[GitHub Actions]] (concept) — `.github/workflows/pages.yml` builds and uploads `site/` on push.
  - fact: Workflow intentionally targets the `demo/` vault, not personal session data.
- [[Claude Code]] (entity) — One of the primary session sources and optional SessionStart hook target.
- [[Codex CLI]] (entity) — Listed alongside Claude and Cursor in example sync output.
- [[Cursor]] (entity) — Contrib-style session source referenced in multi-agent sync examples.
- [[Obsidian]] (entity) — Vault path may be detected during setup for optional adapter use.
