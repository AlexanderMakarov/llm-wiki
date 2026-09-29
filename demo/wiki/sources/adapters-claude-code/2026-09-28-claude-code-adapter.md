---
title: "Claude Code adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, adapters-claude-code, session-ingestion, redaction, live-session-detection, sub-agents]
date: 2026-09-28
source_file: 
project: adapters-claude-code
model: 
last_updated: 2026-09-28
---
## Summary

The Claude Code adapter (v0.1) extracts AI sessions from Anthropic's Claude Code editor and converts them to markdown for [[llmwiki]] ingestion. The adapter parses `.jsonl` records from `~/.claude/projects/`, derives friendly project slugs from encoded file paths, filters record types, performs privacy redaction (dropping thinking blocks and sanitizing secrets by default), and implements live-session detection to skip files modified within the last 60 minutes. It also tags sub-agent sessions separately to enable grouping on project pages.

## Key Claims

1. Claude Code writes sessions as `.jsonl` files to `~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl`, with sub-agent runs stored under `subagents/agent-*.jsonl`.
2. The adapter skips files whose last record is younger than 60 minutes to prevent reading corrupted or incomplete sessions during active work.
3. The adapter derives friendly project slugs by stripping common path prefixes (e.g., `-Users-<user>-Desktop-...-production-draft-`) from the full encoded path; falls back to the last two path components if no marker is found.
4. Known record types (user, assistant) are rendered; internal types (queue-operation, file-history-snapshot, progress) are dropped; unknown types are skipped at DEBUG level without crashing.
5. Thinking blocks are dropped entirely by default; API keys and emails are redacted by pattern matching; username paths are preserved unless `redaction.redact_username` is explicitly enabled.

## Key Quotes

> "If llmwiki reads a file mid-write, it may get a truncated view or corrupt the user's state. To prevent this, the adapter (and `convert.py`) **skips any file whose last record is younger than 60 minutes**."

This design choice prevents data corruption during active sessions and ensures consistent snapshots of completed work.

> "Thinking blocks (`type: "thinking"` inside assistant messages) are **dropped entirely by default**. They're verbose and often contain unredacted reasoning about secrets."

Reflects a conservative privacy stance—verbose internal reasoning is dropped rather than risk leaked sensitive information through partial redaction.

> "**Unknown record types are skipped at DEBUG level** — the converter never crashes on a record it doesn't recognise"

Forward compatibility approach: the adapter gracefully handles new Claude Code versions without code changes, with snapshot tests catching structural changes.

## Connections

- [[Claude Code]] (entity) — the source application whose session files this adapter parses
- [[Adapters]] (entity) — this module is part of the adapter framework for ingesting external sources into the knowledge base
- [[llmwiki]] (entity) — the wiki system that consumes the converted markdown pages
- [[Wiki Synthesis]] (concept) — this adapter executes the extraction phase of the broader session synthesis pipeline

## Contradictions

None identified.