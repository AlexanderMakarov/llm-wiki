---
title: "Configuration Reference (part 4/4: Environment variables)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, environment-variables, adapter-configuration, session-filters]
date: 2026-08-10
source_file: 
project: configuration-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation excerpt (Part 4/4 of Configuration Reference) specifies how to configure llm-wiki via environment variables, `.llmwikiignore` patterns, and per-adapter settings in `config.json`. It documents the deprecation of `LLMWIKI_ROOT`, establishes that non-AI-session adapters (Obsidian, Jira, Meeting transcripts) are opt-in only, and clarifies that most AI adapters are enabled by default except ChatGPT.

## Key Claims

- The `LLMWIKI_ROOT` environment variable is no longer read; vault root is determined solely by `vault.default_path` in `config.json`
- Non-AI-session adapters require explicit opt-in via `{name}.enabled: true` in config to fire during `sync` (ref: #326)
- `.llmwikiignore` supports gitignore-style patterns (wildcards, date patterns, specific filenames) to skip sessions during sync without requiring code changes
- All standard AI-session adapters (Claude Code, Codex CLI, Copilot Chat/CLI, Cursor, Gemini CLI, OpenCode/OpenClaw) are enabled by default
- ChatGPT is the only AI-session adapter that is opt-in by default; configuration requires an explicit `enabled` flag and path to `conversations.json`

## Key Quotes

> "Vault content root is **`vault.default_path` in `config.json`**. The removed `LLMWIKI_ROOT` env var is no longer read." — Clarifies a breaking change from prior environment-variable-driven configuration

> "Non-AI-session adapters are opt-in only (#326) — set `{name}.enabled: true` in this config to have them fire on `sync`." — Establishes the security/privacy model: user data sources (Obsidian, Jira, Meeting) must be explicitly enabled

## Connections

- [[Configuration Reference]] — this is Part 4 of a four-part guide to llm-wiki's config system
- User memory entry [Push & test gotchas](push-and-test-gotchas.md) confirms "LLMWIKI_ROOT removed, `env -u` is a no-op"

## Contradictions

None identified. The documented removal of `LLMWIKI_ROOT` aligns with existing dev memory about configuration changes.