---
title: "Mode B · Agent"
type: source
tags: [wiki-add, raw-doc, session-transcript, mode-b-agent, agent-mode, synthesis-backend, cli-integration, slash-commands]
date: 2026-08-10
source_file: 
project: mode-b-agent
model: 
last_updated: 2026-08-11
---
## Summary

Documents Agent mode (Mode B) in [[llmwiki]] v1.4.0+, a feature that runs wiki synthesis and query operations directly within an existing Claude Code or Codex CLI session, eliminating the need for a separate Anthropic API key. The v1.4.0 release replaced the previous pending-prompt-based agent workflow with a simpler synchronous `claude` CLI backend.

## Key Claims

- Agent mode enables wiki synthesis to execute within the user's existing Claude Code or Codex CLI session without separate API credentials
- v1.4.0 removed the prior `agent` backend (pending-prompt workflow with `synthesize --list-pending`) in favor of a synchronous `claude` CLI backend
- Configuration requires setting `synthesis.backend: "claude"` with optional model selection via `claude_model` parameter
- Six slash commands (`/wiki-sync`, `/wiki-ingest`, `/wiki-query`, `/wiki-reflect`, `/wiki-update`, `/wiki-lint`) dispatch agent workflows from Claude Code
- The `claude` CLI must be on `$PATH` (or configured via `synthesis.claude_path`) for agent mode to function

## Key Quotes

> "Runs synthesis + query **inside** the Claude Code or Codex CLI session that's already open on your machine — no separate Anthropic API key."

Captures the core value proposition: seamless integration without additional infrastructure or credentials.

> "The old `agent` / agent-delegate backend (pending-prompt files + `synthesize --list-pending` / `--complete`) was **removed in v1.4.0**."

Marks a significant architectural simplification in the v1.4.0 release.

## Connections

- [[llmwiki]] — the wiki system whose synthesis engine supports Agent mode as a backend choice
- [[Claude Code]] — the IDE environment in which Agent mode workflows execute via slash commands
- [[Codex CLI]] — an alternative execution environment for Agent mode operations