---
title: "Slash commands reference (part 4/4: Agent-kit skills)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, agent-kit-skills, cli-installation, agent-kit-extension]
date: 2026-09-28
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-28
---
## Summary

Reference documentation for the four skills shipped with the LLM Wiki agent kit (llmwiki-sync, llmwiki-ingest, llmwiki-query, llmwiki-all), which trigger automatically to automate common workflows. Explains installation via `install-agent-kit --dest PATH` to agent directories (Claude Code, Cursor, Codex CLI, etc.), smart upgrading that prunes old copies by content hash, and the process for adding new slash commands with CI-enforced documentation.

## Key Claims

- The kit ships four skills that the model invokes automatically based on their trigger descriptions, eliminating the need to remember slash commands for common tasks
- Skills and commands are installed to configurable destinations (~/.claude for Claude Code, ~/.cursor for Cursor, ~/.codex for Codex CLI, or .claude for a single project)
- Upgrading intelligently prunes old skill copies by content hash while preserving user-edited versions and reporting them as `kept`
- All new slash commands must include a one-line docstring on line 1 and a matching documentation entry with CI enforcement
- Command files use a portable markdown format that can be deployed to different agent directory layouts

## Key Quotes

> "the model invokes these on its own when what you ask for matches their description, so they cover the same work without you remembering a slash command" — describes how skills automate workflows without requiring users to remember commands

> "Upgrading from a release that shipped the skill as `wiki-all` prunes the old copy when you re-run `llmwiki install-agent-kit --dest PATH` (the prune is by content, so a copy you edited is left alone and reported as `kept`)." — explains the intelligent upgrade behavior that preserves edited copies

## Connections

- [[llmwiki]] (entity) — the main project that ships these skills and commands
- [[Claude Code]] (entity) — primary agent using these slash commands via ~/.claude
- [[Cursor]] (entity) — agent using these slash commands via ~/.cursor
- [[Codex CLI]] (entity) — agent using these slash commands via ~/.codex
- [[Agent-Kit Skills]] (concept) — the four built-in skills (llmwiki-sync, llmwiki-ingest, llmwiki-query, llmwiki-all) that trigger automatically based on user requests
- [[Slash Commands]] (concept) — the documentation system and file format for defining agent commands and skills