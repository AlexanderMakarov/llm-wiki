---
title: "Windows setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, windows-setup, path-redaction, bat-scripts, vault-config, git-autocrlf, powershell-execution-policy]
date: 2026-09-08
source_file: 
project: windows-setup
model: 
last_updated: 2026-09-08
---
## Summary

This source documents how to install and run [[llmwiki]] on Windows using `setup.bat`, `sync.bat`, and `build.bat`, with the same external-vault model as Unix. It calls out Windows-specific fixes: use `python` (not `python3`), extend `config.json` redaction for `C:\Users\<you>\`, prefer `git config core.autocrlf input`, and optionally set PowerShell `RemoteSigned` for the current user. [[Claude Code]] session paths under `%USERPROFILE%\.claude\projects\` are handled by the toolchain without manual path configuration.

## Key Claims

- Windows installs require Python ≥ 3.12 and Git; after install, a new terminal is needed so PATH picks up Python, and the venv flow is `python -m venv .venv` then `.venv\Scripts\activate` before `setup.bat`.
- Wiki content (`raw/`, `wiki/`, `site/`) lives in an external vault pointed to by `config.json` `vault.default_path`, not inside the cloned repo—same as macOS/Linux.
- Default username/path redaction covers Unix home patterns but not `C:\Users\<username>\`; Windows users should set `redaction.real_username` and add a matching `extra_patterns` entry with correct JSON/regex escaping (quadruple backslashes in JSON).
- `.bat` wrappers and direct `python -m llmwiki sync|build` are the supported command surface on Windows; there is no automatic Windows SessionStart hook install yet (manual `%USERPROFILE%\.claude\settings.json` only).
- Built static output is opened locally with `start site\index.html`; emoji in terminal output may display poorly due to fonts but does not affect functionality.

## Key Quotes

> "Like the Unix flow, your transcripts/wiki/site live in an external **vault**, not the clone." — separates the git checkout from the durable wiki data directory on Windows as on other platforms.

> "Note: on Windows the command is `python`, not `python3`. The `.bat` files use `python`." — documents the CLI naming difference that breaks copy-paste from Unix docs.

> "The default redaction config covers `/Users/<you>/` and `/home/<you>/` (Unix), but not `C:\Users\<you>\`." — motivates Windows-specific redaction configuration before committing or sharing raw material.

## Connections

- [[llmwiki]] (topic) — Windows install (`setup.bat`), sync/build entry points, vault + `config.json` redaction, and documented platform limitations.
  - fact: Ships parallel `.bat` scripts to Unix shell helpers for sync and static site build.
- [[Claude Code]] (topic) — Optional recommended client on Windows; session JSONL layout under `C:\Users\<you>\.claude\projects\<project>\<uuid>.jsonl`.
  - fact: SessionStart hooks are not auto-installed on Windows via `install.bat`.
- [[Adapters]] (topic) — Ingest path normalization for Windows-style Claude project directories without user path hacks.
  - fact: Tooling is described as handling Windows Claude paths automatically.
- [[Static Site]] (topic) — `build.bat` / `python -m llmwiki build` and opening `site\index.html` with `start`.
  - fact: Site is plain files; no local server required to view output.
