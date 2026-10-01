---
title: "Getting started (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, wiki-setup, installation, vault-configuration, shell-completion]
date: 2026-10-01
source_file: 
project: getting-started
model: 
last_updated: 2026-10-01
---
## Summary

This getting-started guide walks new users through installing llmwiki (requiring Python ≥ 3.12 and git), creating a separate vault directory to store personal session data outside the repository, detecting coding-agent sources via adapters, and executing a first sync to build a browsable wiki. The core design separates code and user data to prevent transcripts from entering version control.

## Key Claims

- llmwiki requires Python ≥ 3.12, `git`, and existing session stores from at least one supported agent on disk
- A bare `llmwiki sync` runs every enabled coding-agent adapter whose data store exists (Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, Gemini)
- The vault directory must reside outside the code repository; when `vault.default_path` is configured, all commands (`sync`, `build`, `synth`, `queue`, `lint`, `init`) automatically target it without requiring a `--vault` flag
- setup.sh / setup.bat is idempotent and installs only one runtime dependency (markdown) via pip, keeping the build stdlib-only with no npm, brew, or database required
- Syntax highlighting runs client-side in the browser via highlight.js, eliminating server-side rendering dependencies
- Shell completion only completes top-level llmwiki commands; flags and nested arguments do not autocomplete
- On macOS, bash users receive `~/.bash_profile` for shell completion instead of `~/.bashrc` because Terminal and iTerm start bash as a login shell

## Key Quotes

> "The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo, so personal data never lands in git."
> — Core architectural principle separating the engine from user data

> "Syntax highlighting runs in the browser via highlight.js, so the build stays stdlib-only."
> — Justifies minimal dependency footprint

> "With `vault.default_path` set, `sync` / `build` / `synth` / `queue` / `lint` / `init` all target the vault automatically — no `--vault` flag needed."
> — Explains UX convenience after initial configuration

## Connections

- [[llmwiki]] (entity) — The core system this guide introduces to new users
  - fact: llmwiki requires Python ≥ 3.12, git, and session stores from at least one supported agent on disk
  - fact: A vault directory outside the repo stores transcripts and wiki pages to prevent personal data from entering git
  - fact: With vault.default_path configured, all commands automatically target the vault without explicit flags

- [[Adapters]] (concept) — The agent-source detection and configuration mechanism
  - fact: `llmwiki sync` runs every enabled adapter for agents whose stores exist on disk
  - fact: Multiple coding agents are supported: Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, Gemini
  - fact: `llmwiki configure-sources` interviews the user about lookback period and enables/disables specific sources

- [[Static Site]] (concept) — The browsable wiki output generated from ingested sessions
  - fact: The vault contains a site/ directory with built HTML ready for viewing in a browser