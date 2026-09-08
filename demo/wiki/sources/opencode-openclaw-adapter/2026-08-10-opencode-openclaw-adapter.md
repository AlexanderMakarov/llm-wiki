---
title: "OpenCode / OpenClaw adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, opencode-openclaw-adapter, schema-normalization, jsonl, platform-detection, ai-integration]
date: 2026-08-10
source_file: 
project: opencode-openclaw-adapter
model: 
last_updated: 2026-09-07
---
## Summary

The OpenCode/OpenClaw adapter for [[llmwiki]] ingests `.jsonl` session transcripts by auto-detecting session stores across Linux, macOS, and Windows platforms. It normalizes the agent-specific schema into Claude-style format for consistent rendering and operates out-of-the-box when the upstream tool is installed.

## Key Claims

- The adapter is classified as an AI-session adapter that auto-fires when its session store is detected on disk
- Session store locations are platform-specific: `~/.config/opencode/sessions/` on Linux, `~/Library/Application Support/opencode/sessions/` on macOS, and `%APPDATA%\opencode\sessions\` on Windows
- Both nested (`<project>/<session>.jsonl`) and flat (`<project>-<session>.jsonl`) directory layouts are supported
- OpenCode's three roles (`user`, `assistant`, `tool`) normalize to Claude-style `{type, message: {role, content}}` records, preserving the `tool` role for distinct rendering
- The adapter has 23 test cases covering its functionality
- Explicit disable is possible via `sessions_config.json` configuration

## Key Quotes

> "Reads `.jsonl` session transcripts written by the OpenCode / OpenClaw agents — both use an identical schema."
— Establishes that OpenCode and OpenClaw share a unified session format, making a single adapter viable.

> "`normalize_records()` translates that schema into the Claude-style `{type, message: {role, content}}` that the shared renderer expects"
— Describes the core schema transformation enabling rendering consistency across heterogeneous agent platforms.

> "Works out-of-the-box if OpenCode / OpenClaw is installed on this machine."
— Reflects the adapter design principle of zero-configuration auto-detection when the upstream tool is available.

## Connections

- [[Adapters]] (concept) — The OpenCode adapter implements the pluggable pattern for session ingestion
  - fact: Auto-fires when a session store is detected, exemplifying AI-session adapter behavior
  - fact: Normalizes external agent schemas into [[llmwiki]]'s shared renderer format
  - fact: Expands support for external AI agents by composing heterogeneous session formats into a unified knowledge base
