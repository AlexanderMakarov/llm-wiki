---
title: "03 · Use with Claude Code"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-03-use-with-claude-code, slash-commands, session-sync, query-interface]
date: 2026-09-28
source_file: 
project: tutorials-03-use-with-claude-code
model: 
last_updated: 2026-09-29
---
## Summary

This tutorial establishes the day-to-day workflow for keeping Claude Code sessions current in llmwiki. It covers verifying the claude_code adapter, installing slash commands, running `/wiki-sync` to ingest sessions, querying the wiki, managing candidate entities, and linting. The core habit is a single `/wiki-sync` after each coding session and `/wiki-query` when recalling prior solutions.

## Key Claims

- Claude Code sessions are automatically discovered from `~/.claude/projects/` by the claude_code adapter
- Slash commands in `.claude/commands/` are auto-loaded by Claude Code when the llm-wiki project is opened
- `/wiki-sync` converts new session `.jsonl` files into raw markdown and triggers auto-ingest, which extracts entities and concepts
- New entities discovered during ingest are placed in `wiki/candidates/` for gated promotion before merging into the canonical wiki
- Incremental syncs take < 5 seconds
- The minimum daily loop is: write code → `/wiki-sync` → `/wiki-candidates` (if needed) → `/wiki-query` to recall

## Key Quotes

> "Claude Code is the source of gravity for most llmwiki users. This tutorial locks in the habits that keep your wiki current: a single `/wiki-sync` after a coding session and a `/wiki-query` when you need to answer 'wait, when did I solve this before?'"

> "The minimum daily loop: Open Claude Code, work on something. /wiki-sync (after the session), /wiki-candidates (if it flagged candidates), /wiki-query <q> (when you need to recall)."

> "Zero errors = wiki is valid. Warnings are fine as long as they're tracked."

## Connections

- [[Claude Code]] (entity) — AI code editor that serves as the primary workspace for llmwiki users; sessions are automatically discovered and ingested
  - fact: Sessions are stored in `~/.claude/projects/` and read by the claude_code adapter
  - fact: Slash commands in `.claude/commands/` are auto-loaded when the llm-wiki project is open
- [[llmwiki]] (entity) — Core CLI system providing commands for sync, ingest, query, and management wrapped as slash commands
  - fact: `/wiki-sync` converts new session files and triggers auto-ingest
  - fact: `/wiki-query` searches the knowledge base and returns answers with inline `[[wikilinks]]` to sources
- [[Adapters]] (entity) — Plugin system for reading external data sources; the claude_code adapter reads and processes Claude sessions
  - fact: Adapter presence is verified with `python3 -m llmwiki adapters | grep claude_code`
  - fact: Auto-ingest after sync discovers new entities and concepts from session content
- [[Wiki Synthesis]] (concept) — Process of converting raw sessions into indexed, queryable wiki pages through sync and ingest steps
  - fact: Sync reads `.jsonl` session files and writes raw markdown pages
  - fact: Auto-ingest enriches pages with entity and concept extraction
- [[Wikilinks]] (concept) — Bidirectional link syntax used in query results to connect users back to source sessions

## Contradictions

None identified.