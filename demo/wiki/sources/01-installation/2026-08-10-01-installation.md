---
title: "01 · Installation"
type: source
tags: [wiki-add, raw-doc, session-transcript, 01-installation, local-first, cli-setup]
date: 2026-08-10
source_file: 
project: 01-installation
model: 
last_updated: 2026-08-11
---
## Summary

Installation tutorial for [[llmwiki]], a local-first CLI tool for synthesizing AI session transcripts into structured wiki pages. Setup takes ~5 minutes via a single idempotent script; the tool runs entirely offline with no telemetry, accounts, or network calls at build time. PyPI and Homebrew distribution channels are planned but not yet available.

## Key Claims

- llmwiki runs entirely on the user's machine with no telemetry, accounts, or network calls required at build time
- Installation requires Python 3.12+, git, and an existing AI-coding agent with session history stored locally
- The setup process is accomplished via a single idempotent shell script that creates required directories, seeds initial wiki files, and installs the markdown package dependency
- CLI functionality can be verified via `python3 -m llmwiki --version` and `python3 -m llmwiki adapters` (which lists configured agent adapters)
- Optional installation paths via PyPI (`#246`) and Homebrew (`#247`) are under development; clone-and-run is currently authoritative
- Docker deployment is supported as a zero-dependency alternative

## Key Quotes

> "llmwiki runs **locally**. Every session transcript stays on your machine. No telemetry, no account, no network calls at build time."

— Establishes the core privacy-first design principle

> "The setup script is idempotent. Running it twice is safe."

— Indicates defensive, user-friendly design that tolerates accidental re-runs

## Connections

- [[llmwiki]] — the main product being installed and configured

## Contradictions

None identified. The tutorial's header, its verification step, and its troubleshooting section all state Python 3.12 as the minimum, matching what the project requires.