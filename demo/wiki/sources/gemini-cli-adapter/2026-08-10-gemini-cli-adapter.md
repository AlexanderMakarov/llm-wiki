---
title: "Gemini CLI adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, gemini-cli-adapter, adapters, session-ingestion, jsonl]
date: 2026-08-10
source_file: 
project: gemini-cli-adapter
model: 
last_updated: 2026-08-11
---
## Summary

Documentation for the Gemini CLI adapter was added to [[LLMWiki]], describing a production-ready tool (v0.5) for ingesting AI session histories from [[GeminiCLI]] storage directories. The adapter automatically derives project identifiers from directory structure and supports configurable root paths.

## Key Claims

- The Gemini CLI adapter (module `llmwiki.adapters.contrib.gemini_cli`) is at production status v0.5
- [[GeminiCLI]] stores session history in one of three standard locations: `~/.gemini/`, `~/.config/gemini/`, or `~/.local/share/gemini/`
- Project slugs are derived by lowercasing the first subdirectory name and prefixing with `gemini-`; files stored in root receive slug `gemini-root`
- Only schema version "v1" is supported
- Custom root paths can be configured via `config.json` under `adapters.gemini_cli.roots`
- The adapter discovers `.jsonl` files as well as Gemini's native `chat-*.json` and `session-*.json` export formats

## Key Quotes

> "Uses the first directory under the root, lowercased and prefixed with `gemini-`" — explains automatic project slug derivation from directory structure

> "Files directly in the root get slug `gemini-root`" — edge case handling for root-level session files

## Connections

- [[LLMWiki]] — the project containing this adapter
- [[GeminiCLI]] — the external tool whose sessions are ingested