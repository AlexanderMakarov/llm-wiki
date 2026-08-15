---
title: "03 · Use with Claude Code"
type: source
tags: [wiki-add, raw-doc, session-transcript, 03-use-with-claude-code, slash-commands, wiki-sync, session-ingestion, candidates-workflow, daily-workflow]
date: 2026-08-10
source_file: 
project: 03-use-with-claude-code
model: 
last_updated: 2026-08-11
---
## Summary

This tutorial documents the core daily workflow for maintaining an llmwiki instance integrated with Claude Code. It establishes the habit of syncing new sessions with `/wiki-sync`, querying the wiki for recalled knowledge, and reviewing candidate entities before promotion. The workflow is designed for minimal overhead: a single slash command after each session plus on-demand queries and linting.

## Key Claims

- The llmwiki adapter for Claude Code reads from `~/.claude/projects/` and can be verified with `python3 -m llmwiki adapters | grep claude_code`
- Slash commands are auto-discovered by Claude Code from `.claude/commands/` when the llm-wiki project is opened
- `/wiki-sync` is incremental (< 5 seconds) and converts `.jsonl` session files to raw wiki pages, with optional auto-ingest and auto-build
- New discovered entities are created as candidates in `wiki/candidates/entities/` with `status: candidate` for manual review before promotion to the main wiki
- The `/wiki-lint` command enforces 17 structural lint rules (link integrity, orphan detection, cache tier consistency) and returns `0 errors` as the success criterion
- Operations are appended to `wiki/log.md` in a grep-parseable format (queryable with `grep "^## \["`)

## Key Quotes

> "Claude Code is the source of gravity for most llmwiki users. This tutorial locks in the habits that keep your wiki current: a single `/wiki-sync` after a coding session and a `/wiki-query` when you need to answer 'wait, when did I solve this before?'"

This establishes the philosophy: automation should reduce cognitive overhead to a single command per session.

> "Each action is non-destructive: discarded candidates land under `wiki/archive/candidates/` with a reason file."

Reflects the conservative design: new entities are never lost, only archived with rationale.

## Connections

- [[Claude Code]] — the IDE that generates sessions for ingestion
- [[llmwiki CLI]] — the underlying tool invoked by slash commands
- [[Wiki ingestion]] — the process converting `.jsonl` → raw pages
- [[Candidates workflow]] — the editorial gate for entity promotion
- [[Wiki lint]] — the health-check system for structural consistency

## Contradictions

None identified.