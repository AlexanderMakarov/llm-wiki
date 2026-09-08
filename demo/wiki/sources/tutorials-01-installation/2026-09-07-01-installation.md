---
title: "01 · Installation"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-01-installation, python-dependencies, distribution, cli-setup]
date: 2026-09-07
source_file: raw/docs/tutorials-01-installation/01-installation.md
project: tutorials-01-installation
model: 
last_updated: 2026-09-07
---
## Summary

This tutorial documents four installation paths for [[llmwiki]]: PyPI (`llm-wiki-plus`), Homebrew (pending issue #212), local clone with setup scripts, and Docker. It covers prerequisites (Python 3.12+, git), post-installation verification via `llmwiki adapters`, and troubleshooting. The design emphasizes local-only operation with no telemetry or network dependencies.

## Key Claims

- llmwiki requires Python 3.12 or newer; Python 3.11 and older will raise `ImportError`.
- The PyPI package name is `llm-wiki-plus` (not `llmwiki`) because PyPI already has an unrelated package named `llmwiki` and rejects `llm-wiki` as too similar.
- llmwiki runs entirely locally with no telemetry, accounts, or network calls at build time; all session transcripts remain on the user's machine.
- The `llmwiki adapters` command verifies which AI-coding agents have session stores on the machine and which are configured for syncing.
- Setup scripts (`setup.sh` on Unix, `setup.bat` on Windows) are idempotent and scaffold the `raw/`, `wiki/`, and `site/` directory structure.

## Key Quotes

> "llmwiki runs **locally**. Every session transcript stays on your machine. No telemetry, no account, no network calls at build time." — Establishes the architectural principle underlying the installation and usage model.

> "The PyPI distribution name is `llm-wiki-plus` (PyPI already has an unrelated `llmwiki`, and rejects `llm-wiki` as too similar)." — Clarifies a packaging naming quirk that could confuse first-time users searching for the package.

## Connections

- [[llmwiki]] (project) — the CLI tool and documentation system being installed
  - fact: Four installation methods accommodate different environments (PyPI, Homebrew, source clone, Docker).
  - fact: Minimum required Python version is 3.12.
  
- [[Adapters]] (component) — integrations for external session transcript sources, including AI-coding agents
  - fact: Post-install verification via `llmwiki adapters` shows which agents are configured for syncing.

- [[Configuration]] (system) — setup and initialization of vaults and agent connections
  - fact: `llmwiki init --vault .` scaffolds directory structure; full agent configuration is deferred to the next tutorial.
