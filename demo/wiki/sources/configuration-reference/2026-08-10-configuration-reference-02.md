---
title: "Configuration Reference (part 2/4: Config file (config.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, config-json, session-converter, redaction-patterns, adapters, truncation]
date: 2026-08-10
source_file: 
project: configuration-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation section presents the complete schema for `config.json`, the configuration file used by the session converter to control filtering, redaction, truncation, and adapter behavior. It provides the full JSON schema with sections for filters (session selection), redaction (sensitive data masking), truncation (output size limits), drop_thinking_blocks (LLM thinking removal), and adapters (data source integration). The file is local, gitignored, and automatically loaded from the repository root.

## Key Claims

- `config.json` is gitignored and auto-loaded by the converter when present at repo root
- Configuration is organized into five sections: filters, redaction, truncation, drop_thinking_blocks, and adapters
- The filters section allows exclusion by project, record type, and session properties (headless status, temp working directory)
- Redaction patterns include regex expressions for masking API keys, secrets, tokens, bearers, passwords, and email addresses
- Output truncation enforces size limits: tool results (500 chars), bash stdout (5 lines), write previews (5 lines), user prompts (4000 chars), assistant text (8000 chars)
- Four adapters are supported for session ingestion: Obsidian (with vault paths and folder exclusions), Codex CLI, Gemini CLI, and OpenClaw (with configurable root paths)

## Key Quotes

> "`config.json` is gitignored. The converter auto-loads it if present at the repo root."

Indicates that configuration is local-only and doesn't require explicit command-line specification.

> "Copy the example and edit: `cp examples/sessions_config.json config.json`"

The recommended initial setup workflow.

## Connections

- [[Configuration Reference]] — this documentation is part 2 of 4 of the configuration reference guide

## Contradictions

None identified.