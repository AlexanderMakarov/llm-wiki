---
title: "Configuration (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, config-schema, synthesis-backend, lean-mode, redaction, incremental-synthesis]
date: 2026-08-10
source_file: 
project: configuration
model: 
last_updated: 2026-08-11
---
## Summary

Configuration documentation for [[llmwiki]]. Covers setup of config.json, redaction and truncation settings, synthesis backend selection (dummy/ollama/claude), and state tracking for incremental synthesis. Key features include lean mode for Claude synthesis, which reduces costs ~9x by stripping unnecessary context, and downgrade protection that prevents accidental overwriting of real synthesis pages with stubs.

## Key Claims

- `config.json` is auto-loaded from the current directory and gitignored, allowing users to customize settings locally without committing them to version control
- Claude synthesis runs in "lean mode" by default, stripping tool schemas, MCP servers, skills, and agent system prompt, reducing costs by approximately 9x per page
- Synthesis is incremental: `llmwiki-state.json` tracks modification times per raw file, so only new or changed files are processed on subsequent runs; the daily LLM bill scales with new content, not corpus size
- The system refuses downgrade from real synthesis pages to dummy stub pages even under `--force`, protecting pages with real content from accidental overwriting (reported as `protected` in run summary)
- The `LLMWIKI_ROOT` environment variable has been removed; vault root path is now configured via `vault.default_path` in config.json
- Redaction can be configured with Python regex patterns to automatically scrub API keys, tokens, passwords, and email addresses from raw output

## Key Quotes

> "That is ~9x cheaper per page, measured — see reference/synthesis-cost.md for the numbers and for why `claude_model` defaults to sonnet rather than a cheaper model."
— Documenting measured cost savings of lean mode and justifying sonnet as the default model

> "The pipeline now refuses that downgrade: stub output is never written over a real page, even under `--force` — such pages are reported as `protected` in the run summary."
— Describing the safety mechanism that prevents accidental replacement of real synthesis with canned stubs

> "Synthesis is incremental. `<vault>/llmwiki-state.json` (`synth.files`) records an mtime per raw file; a nightly `sync`/`synthesize` only processes files that are new or changed since the last run — the daily LLM bill is proportional to new content, not to corpus size."
— Explaining how state tracking enables cost-proportional synthesis

## Connections

- [[llmwiki]] — this document serves as the authoritative configuration reference for the system

## Contradictions

(none)