---
title: "OpenClaw adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, openclaw-adapter, session-ingestion, jsonl, configuration]
date: 2026-08-10
source_file: 
project: openclaw-adapter
model: 
last_updated: 2026-08-11
---
## Summary

Documentation for the OpenClaw adapter, an AI-session adapter that automatically ingests `.jsonl` session transcripts from the OpenClaw agent gateway. It supports both native installation paths and Syncthing vault inbox mirrors, with configurable roots via `config.json`.

## Key Claims

- Activates by default when the session store exists at `~/.openclaw/agents/`
- Reads `.jsonl` transcripts in two directory layouts: native (`<agent>/sessions/<uuid>.jsonl`) and vault inbox mirror (`<agent>/<uuid>.jsonl`)
- Filters JSONL records by `type == "message"` and flattens user content for rendering
- Root paths can be overridden in `config.json` to point to alternate locations, including Syncthing vault inboxes
- Skips `*.trajectory.jsonl`, `*.checkpoint.*.jsonl`, and anything under `_quarantine/` directories

## Key Quotes

> "native store under `~/.openclaw/agents/`, not the OpenCode app-config layout — that is the separate [`opencode`](opencode.md) adapter" — distinguishes this from the related OpenCode adapter despite both relating to OpenClaw ecosystems

> "Only `type == "message"` rows become conversation turns; user `content` lists are flattened to strings for the shared renderer" — explains how JSONL records are filtered and transformed into conversation turns

## Connections

- [[OpenCode adapter]] — separate adapter for OpenCode app-config schema; this one handles OpenClaw's native agent gateway instead

## Contradictions

None identified.