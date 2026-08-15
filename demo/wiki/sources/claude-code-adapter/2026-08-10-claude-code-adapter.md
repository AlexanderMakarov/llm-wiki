---
title: "Claude Code adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, claude-code-adapter, session-format, live-session-detection, redaction, sub-agent]
date: 2026-08-10
source_file: 
project: claude-code-adapter
model: 
last_updated: 2026-08-11
---
## Summary

This documentation describes the Claude Code adapter (v0.1 production), which ingest `.jsonl` session files from `~/.claude/projects/` and converts them to wiki pages. Key features include path-based project slug derivation, live-session detection to avoid reading mid-write files (default 60-minute threshold), treatment of sub-agent runs as separate wiki pages with `is_subagent: true` frontmatter, and graceful forward compatibility via dropping unknown record types at DEBUG level rather than crashing.

## Key Claims

- Claude Code encodes the full absolute path as the directory name (slashes → dashes); the adapter strips a common prefix marker (`draft`, `production`, or `Desktop`) and derives a friendly slug, or falls back to the last two path components if the marker is missing.
- The adapter parses five known record types (`user`, `assistant`, `queue-operation`, `file-history-snapshot`, `progress`) and drops unrecognized ones at DEBUG level instead of failing, enabling forward compatibility with future Claude Code versions.
- Sessions are skipped by default if their last record is younger than 60 minutes; this prevents reading a file mid-write and corrupting the user's live session state; override with `--include-current` or config.
- Thinking blocks (`type: "thinking"` inside assistant messages) are dropped entirely by default because they often contain unredacted reasoning about secrets.
- Sub-agent sessions (from `Task` or `Agent` tools) are written to `subagents/agent-*.jsonl` and ingested as separate wiki pages tagged with `is_subagent: true`, enabling grouping under the parent session on project pages.
- The adapter supports only Claude Code 2.x schema (tested against 2.1.87); structural changes will be caught by snapshot test diffs.

## Key Quotes

> "Unknown record types are skipped at DEBUG level — the converter never crashes on a record it doesn't recognise" — design principle for handling schema evolution without breaking.

> "A session that ended more than an hour ago → converted on next sync; A session that ended 5 minutes ago → skipped until the next sync that runs more than an hour after it ended" — articulates the live-session safety tradeoff: timeliness vs. avoiding mid-write reads.

> "Thinking blocks […] are dropped entirely by default. They're verbose and often contain unredacted reasoning about secrets." — justifies aggressive redaction posture for model internals.

> "File naming for sub-agents: `raw/sessions/<project>/<date>-<parent-slug>-subagent-<agent-id-8>.md`" — specifies the naming convention that enables parent–child session relationships.

## Connections

- [[Claude Code]] — the external tool whose session files the adapter reads; format and directory structure are determined by Claude Code's implementation.
- [[llmwiki]] — the larger system for which the adapter provides ingest from Claude Code projects into the wiki vault.