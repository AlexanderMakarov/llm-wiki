---
title: "Multi-Agent Setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, multi-agent-setup, adapters, auto-detection, idempotent-sync, agent-configuration]
date: 2026-08-10
source_file: 
project: multi-agent-setup
model: 
last_updated: 2026-08-11
---
## Summary

llmwiki ingests sessions from multiple coding agents through an adapter-based architecture supporting seven tools. The system uses auto-detection to identify available agents by checking for session store paths on disk and requires no configuration by default. Syncing is idempotent via file modification time tracking, and the wiki ingestion layer treats all sessions uniformly regardless of originating agent once they reach the `raw/` directory.

## Key Claims

- Seven coding agents are currently supported: [[Claude Code]], [[Codex CLI]], [[GitHub Copilot]], [[Cursor]], [[Gemini CLI]], and [[Obsidian]]; GitHub Copilot has separate adapters for Chat (VS Code) and CLI
- Production-ready adapters exist for Claude Code, Codex CLI, Copilot Chat/CLI, and Obsidian; Cursor and Gemini CLI remain in scaffold status with incomplete implementations
- Auto-detection requires zero configuration: the system imports adapters, calls `is_available()` to check session store paths, and runs only the available adapters
- Sync is idempotent via state tracking in `llmwiki-state.json` using file modification times; re-running on unchanged files is a no-op
- Each agent derives a unique project slug from its session store layout, preventing cross-agent session collisions
- Adapter paths and session store locations are fully configurable per-agent via `config.json`
- Once ingested to `raw/`, the wiki layer processes sessions identically regardless of source agent

## Key Quotes

> "When you run `llmwiki sync`, the system: Imports every adapter in `llmwiki/adapters/`, Calls `is_available()` on each — this checks whether the session store path exists on disk, Runs only the available adapters" — the auto-discovery mechanism eliminating configuration overhead

> "The sync is idempotent. State is tracked in `llmwiki-state.json` by file mtime, so re-running on unchanged files is a fast no-op." — justifies safe, repeatable sync operations

> "Each agent gets its own project slug derived from its session store layout, so sessions from different agents never collide." — the isolation mechanism preventing cross-adapter conflicts

## Connections

- [[Claude Code]] — production adapter reading from `~/.claude/projects/`; supports sub-agents
- [[GitHub Copilot]] — two production adapters (Chat in VS Code workspaceStorage, CLI in `~/.copilot/session-state/`)
- [[Codex CLI]] — OpenAI's tool; adapter normalizes native JSONL schema to shared format
- [[Cursor]] — IDE adapter with SQLite record parsing in progress
- [[Gemini CLI]] — Google's CLI; schema and paths under development
- [[Obsidian]] — vault adapter with configurable paths, folder exclusions, and minimum content filtering

## Contradictions

None identified.