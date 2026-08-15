---
title: "Getting started (part 2/2: Auto-sync on session start (optional))"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, auto-sync, session-start-hooks, background-processes]
date: 2026-08-10
source_file: 
project: getting-started
model: 
last_updated: 2026-08-11
---
## Summary

This documentation excerpt explains how to enable automatic synchronization for the [[llm-wiki]] project by configuring a `SessionStart` hook in Claude Code's settings. The setup runs convert.py in the background using a non-blocking shell pattern (`( ... &) ; exit 0`) to ensure the sync process never delays Claude Code startup.

## Key Claims

- Auto-sync for llm-wiki can be configured via a `SessionStart` hook entry in `~/.claude/settings.json`
- The sync command must use the `( ... &) ; exit 0` pattern to background the process and exit immediately
- This pattern ensures the conversion sync runs independently without blocking Claude Code session startup
- The absolute path to convert.py must be specified in the hook configuration

## Key Quotes

> "The `( ... &) ; exit 0` pattern backgrounds the sync and makes sure it never blocks Claude Code starting."

This captures the core design principle: preventing auto-sync from interfering with interactive session launch.

## Connections

- [[llm-wiki]] — the project for which this auto-sync configuration is designed
- [[Claude Code]] — the integration that provides the SessionStart hook mechanism

## Contradictions

None noted.