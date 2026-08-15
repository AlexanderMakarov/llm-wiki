---
title: "Getting started (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, installation, vault-architecture, multi-agent-support]
date: 2026-08-10
source_file: 
project: getting-started
model: 
last_updated: 2026-08-11
---
## Summary

This is the first part of the Getting started guide for [[llm-wiki]]. It covers prerequisites (Python ≥ 3.12, git, and existing agent session stores), a 5-minute install workflow (clone, venv, setup.sh), vault setup (separate personal data directory), adapter detection, and the three core commands (sync, synth, build). The guide emphasizes the architectural decision to keep transcripts and wiki pages outside the git repo in an isolated vault, so personal data never lands in version control.

## Key Claims

- llm-wiki auto-detects which agents are installed (Claude Code, Codex CLI, Copilot Chat/CLI, Cursor, Gemini CLI) with no configuration needed
- A separate **vault** directory outside the repo holds all transcripts, wiki pages, and the built site; the repo itself contains only code and demo seeds
- `setup.sh` / `setup.bat` is idempotent and only installs the `markdown` runtime dep; syntax highlighting runs in the browser via highlight.js, keeping the build stdlib-only
- With `vault.default_path` set in `config.json`, all commands (sync, synth, build, etc.) target the vault automatically without requiring `--vault` flags
- Building the actual wiki requires an LLM in the loop (Karpathy layer 2), called via `/wiki-ingest` inside a Claude Code session
- The PDF adapter was removed in a simplification sweep and no longer appears in `llmwiki adapters` output

## Key Quotes

> "No `npm`, no `brew`, no database, no account." — describes the minimal prerequisites and dependency footprint

> "Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo, so personal data never lands in git." — core architecture principle protecting user privacy

> "With `vault.default_path` set, `sync` / `build` / `synth` / `queue` / `lint` / `init` all target the vault automatically — no `--vault` flag needed." — convenience feature reducing repetitive configuration

## Connections

- [[Multi-Agent Support]] — documents support for Claude Code, Codex CLI, Copilot (Chat and CLI), Cursor, and Gemini CLI simultaneously with colored agent badges
- [[Vault Architecture]] — introduces the concept of personal data isolation outside the repo
- [[CLAUDE.md]] — referenced for the full Ingest Workflow when using Claude Code to build wiki pages from raw sessions
- [[README.md]] — references the rationale section on personal data staying outside the repo

## Contradictions

- None detected (this is documentation, not a report of conflicting experiences).