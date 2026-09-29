---
title: "Mode B · Agent"
type: source
tags: [wiki-add, raw-doc, session-transcript, modes-agent-index, agent-mode, synthesis-backend, slash-commands]
date: 2026-09-28
source_file: 
project: modes-agent-index
model: 
last_updated: 2026-09-28
---
## Summary

This document describes Agent Mode (v1.4.0+) in [[llmwiki]], which runs synthesis and queries inside existing [[Claude Code]] or [[Codex CLI]] sessions without requiring a separate Anthropic API key. The old agent-delegate backend (pending-prompt files + `synthesize` commands) was removed and replaced with a `claude` backend that uses synchronous `claude -p` invocations. Slash commands (`/wiki-sync`, `/wiki-ingest`, `/wiki-query`, `/wiki-reflect`, `/wiki-update`, `/wiki-lint`) drive the workflow, and the configuration requires setting `synthesis.backend: "claude"`.

## Key Claims

- Agent Mode eliminates the need for a separate API key by routing synthesis inside the user's existing Claude Code or Codex CLI session
- The agent-delegate backend with pending-prompt files was removed in v1.4.0; it was replaced by a synchronous `claude` backend configuration
- Slash commands installed to `~/.claude/commands/` provide the primary interface for Agent Mode workflows
- The `claude` CLI must be available on `$PATH` (or configured explicitly via `synthesis.claude_path`)
- `llmwiki add` rebuilds the site by default; `--synthesize` includes wiki source generation in a single invocation

## Key Quotes

> "Runs synthesis + query **inside** the Claude Code or Codex CLI session that's already open on your machine — no separate Anthropic API key."
- Defines the core architecture: synthesis executes within the user's existing editor session.

> "The old `agent` / agent-delegate backend (pending-prompt files + `synthesize --list-pending` / `--complete`) was **removed in v1.4.0**."
- Documents a breaking change; users upgrading must migrate to the `claude` backend.

## Connections

- [[llmwiki]] (entity) — the system implementing Agent Mode
  - fact: Agent Mode runs synthesis and queries synchronously inside Claude Code or Codex CLI sessions.
- [[Claude Code]] (entity) — one target environment for Agent Mode
  - fact: Slash commands are installed and executed within Claude Code.
- [[Codex CLI]] (entity) — the other target environment for Agent Mode
  - fact: Existing Codex CLI sessions can run wiki commands without additional API setup.
- [[Wiki Synthesis]] (concept) — the core process executed in Agent Mode
  - fact: Synthesis backend configuration controls whether synthesis runs via `claude` CLI or external infrastructure.

## Contradictions

None identified.