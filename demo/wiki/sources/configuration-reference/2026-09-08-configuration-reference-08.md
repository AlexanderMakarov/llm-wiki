---
title: "Configuration Reference (part 8/8: .llmwikiignore)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, llmwikiignore, adapter-configuration, sync-filters, session-sync, config-json]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
## Summary

This installment closes the **Configuration Reference** with `.llmwikiignore`, a repo-root gitignore-style file whose patterns exclude matching sessions from `sync`, and documents the `adapters` block in `config.json`: registry key names, default enablement (auto for coding-agent stores vs opt-in for exports and integrations), and per-adapter fields including shared `roots`, `enabled`, and `since`. It states that bare `llmwiki sync` runs every ingest-ready adapter whose store exists and is not disabled, that non-session intake requires `enabled: true` (#326), and points readers to `llmwiki configure-sources` and the multi-agent setup map for path probing and lookback.

## Key Claims

- Sessions whose paths match any line in `.llmwikiignore` are skipped during sync; comments (`#`) and blank lines are ignored.
- Adapter keys under `adapters` in `config.json` must match each adapter’s registry name (e.g. `claude_code`, `cursor_ide`, `obsidian`).
- Claude Code, Codex CLI, Copilot Chat/CLI, Cursor IDE/CLI, Gemini CLI, OpenCode, and OpenClaw default to auto enablement when their session store is present; ChatGPT, Obsidian, Jira, and meeting transcripts require explicit `enabled: true`.
- Every adapter accepts optional `since` (`YYYY-MM-DD` or `"all"`); a top-level `filters.since` can apply globally alongside per-adapter overrides.
- Cursor IDE is the only listed adapter with an extra `global_db` field; ChatGPT uses `export_dirs` and `min_messages`; Obsidian uses `vault_paths`, `exclude_folders`, and `min_content_chars`; Jira uses server credentials and `jql`.

## Key Quotes

> "Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync." — defines `.llmwikiignore` behavior relative to the vault pipeline.

> "Bare `llmwiki sync` runs every ingest-ready coding-agent adapter whose store is present and not explicitly disabled." — default sync scope without opt-in adapters.

> "Notes/export intake needs `enabled: true` (#326)." — separates automatic agent-store sync from Obsidian, exports, and similar sources.

## Connections

- [[llmwiki]] (entity) — product whose sync and configuration model this reference describes.
  - fact: Session filtering and adapter blocks are first-class parts of vault sync, not ad hoc CLI flags only.
- [[Configuration Reference]] (concept) — canonical doc series; this page is part 8/8 covering ignore rules and adapter tables.
- [[Adapters]] (concept) — pluggable session and intake sources; each row maps registry name to `config.json` key and fields.
- [[Claude Code]] (entity) — `claude_code` adapter; auto when store present; `roots`, `enabled`, `since`.
- [[Codex CLI]] (entity) — `codex_cli` adapter; same default pattern as other core coding agents.
- [[Cursor]] (entity) — `cursor_ide` (bare sync when enabled / store present, plus `global_db`) and `cursor_cli` adapters.
- [[Gemini CLI]] (entity) — `gemini_cli` in the auto-when-present adapter set.
- [[Obsidian]] (entity) — opt-in `obsidian` adapter for notes intake via `vault_paths` and related filters.
- [[GitHub Copilot]] (entity) — `copilot_chat` and `copilot_cli` adapters with optional custom `roots` (example shows workspaceStorage path).
