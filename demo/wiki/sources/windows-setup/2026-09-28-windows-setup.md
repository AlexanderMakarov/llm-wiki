---
title: "Windows setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, windows-setup, python-windows-path, git-autocrlf, redaction-config, powershell-execution]
date: 2026-09-28
source_file: 
project: windows-setup
model: 
last_updated: 2026-09-29
---
## Summary

This document provides comprehensive Windows-specific installation and configuration guidance for [[llmwiki]]. It covers Python 3.12+ installation with PATH configuration, Git prerequisites, running commands via `.bat` wrapper scripts, handling Windows paths in redaction patterns, Git line ending configuration (`core.autocrlf`), and PowerShell execution policy requirements. The document identifies current Windows-specific limitations (no SessionStart hook, no GPG signing setup, emoji rendering).

## Key Claims

- llmwiki ships `.bat` wrapper scripts alongside Unix shell scripts for transparent Windows CLI compatibility
- Python on Windows must be installed with "Add Python to PATH" checkbox enabled; if `setup.bat` fails, reopening the terminal picks up the new PATH
- Redaction patterns in `config.json` for Windows usernames require quadruple-escaped backslashes due to JSON and regex escaping layers
- Git on Windows defaults to `core.autocrlf=true` but the repository recommends `core.autocrlf=input`
- PowerShell may require `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` to execute `.bat` files
- Claude Code on Windows automatically handles Unix-like session path formats at `C:\Users\<you>\.claude\projects\<project>\<uuid>.jsonl` without user intervention

## Key Quotes

> "Like the Unix flow, your transcripts/wiki/site live in an external **vault**, not the clone." — establishes vault separation as a consistent architectural principle across platforms

> "Note the quadruple backslashes — JSON string escaping + regex escaping." — highlights a critical but subtle Windows-specific configuration detail for path redaction

> "This is a Windows terminal font issue — everything still works, it just looks odd." — characterizes emoji rendering as a known cosmetic limitation with no functional impact

## Connections

- [[llmwiki]] (entity) — the subject of this setup guide; Windows is a supported installation platform
  - fact: Windows installation uses the same vault-based architecture as Unix/macOS
  - fact: Command execution via `.bat` files is functionally equivalent to Unix shell scripts

- [[Configuration]] (entity) — central to Windows customization and security
  - fact: Redaction config on Windows requires regex patterns with quadruple-escaped backslashes in `config.json`
  - fact: `config.json` vault path settings work identically across platforms

- [[Claude Code]] (entity) — optional but recommended IDE for Windows development
  - fact: Claude Code on Windows stores sessions at Unix-style paths that llmwiki handles transparently

- [[Static Site]] (concept) — the generated output is plain HTML files executable without a server
  - fact: Windows users can open the site directly via `start site\index.html`

## Contradictions

None identified.