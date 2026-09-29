---
title: "Configuration Reference (part 8/8: .llmwikiignore)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, adapter-configuration, sync-lookback, llmwikiignore]
date: 2026-09-28
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-28
---
## Summary

Documentation of [[llmwiki]]'s configuration system covering pattern-based session filtering and per-adapter configuration. Defines 13 adapters across coding assistants, note-taking, and external services, with two distinct auto-enablement policies: coding-agent adapters auto-enable when stores are present, while note-intake and export adapters require explicit opt-in.

## Key Claims

- `.llmwikiignore` files use gitignore-style patterns to exclude sessions from sync during `llmwiki sync` runs.
- Coding-agent [[Adapters]] (Claude Code, Codex CLI, Cursor) auto-enable when their data stores exist; note-intake and export adapters (Obsidian, Jira, ChatGPT, Meeting) require `enabled: true` in config.json.
- All adapters accept an optional `since` parameter (`YYYY-MM-DD` or `"all"`) to control sync lookback windows.
- Bare `llmwiki sync` runs only ingest-ready coding-agent adapters whose stores are present and not explicitly disabled.
- The `llmwiki configure-sources` command probes paths, sets lookbacks, and writes adapter settings.

## Key Quotes

> "Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync."
- Explains the core function of `.llmwikiignore`

> "Bare `llmwiki sync` runs every ingest-ready coding-agent adapter whose store is present and not explicitly disabled. Notes/export intake needs `enabled: true`."
- Clarifies the divergent default-enablement policies

## Connections

- [[llmwiki]] (entity) — the system whose configuration is documented
- [[Adapters]] (entity) — central topic; defines configuration schema and auto-enablement policies for all 13 adapter types
  - fact: Coding-agent adapters auto-enable when stores are present; note and export adapters require explicit opt-in
  - fact: All adapters support optional `since` parameter for configurable lookback windows
- [[Claude Code]] (entity) — documented as auto-enabling adapter with `roots`, `enabled`, `since` fields
- [[Codex CLI]] (entity) — auto-enabling coding adapter
- [[Cursor]] (entity) — both "Cursor IDE" and "Cursor Agent CLI" documented; IDE variant supports additional `global_db` configuration
- [[Obsidian]] (entity) — documented as opt-in note adapter with `vault_paths`, `exclude_folders`, `min_content_chars` configuration
- [[Gemini CLI]] (entity) — auto-enabling coding adapter
- [[GitHub Copilot]] (entity) — "Copilot Chat" and "Copilot CLI" adapters documented as auto-enabling