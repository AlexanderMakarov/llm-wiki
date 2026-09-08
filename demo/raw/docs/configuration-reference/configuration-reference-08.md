---
title: "Configuration Reference (part 8/8: .llmwikiignore)"
slug: configuration-reference-08
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 8 of 8 of **Configuration Reference** — .llmwikiignore.

## `.llmwikiignore`

Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync.

```
# Skip a whole project
confidential-client/*

# Skip anything before a date
*2025-11-*

# Skip a specific session
ai-newsletter/2026-04-04-*secret*

# Comments start with #
# Blank lines are ignored
```

## Per-adapter configuration

Each adapter can be configured in the `adapters` section of `config.json`. The key must match the adapter's registry name.

| Adapter | Config key | Default enablement | Configurable fields |
|---|---|---|---|
| Claude Code | `claude_code` | Auto when store present | `roots`, `enabled`, `since` |
| Codex CLI | `codex_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Copilot Chat | `copilot_chat` | Auto when store present | `roots`, `enabled`, `since` |
| Copilot CLI | `copilot_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Cursor IDE | `cursor_ide` | Bare sync when enabled / store present | `roots`, `enabled`, `since`, `global_db` |
| Cursor Agent CLI | `cursor_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Gemini CLI | `gemini_cli` | Auto when store present | `roots`, `enabled`, `since` |
| OpenCode | `opencode` | Auto when store present | `roots`, `enabled`, `since` |
| OpenClaw | `openclaw` | Auto when store present | `roots`, `enabled`, `since` |
| ChatGPT | `chatgpt` | Opt-in (`enabled: true`) | `enabled`, `export_dirs`, `min_messages`, `since` |
| Obsidian | `obsidian` | Opt-in (`enabled: true`, notes intake) | `vault_paths`, `exclude_folders`, `min_content_chars`, `since` |
| Jira | `jira` | Opt-in (`enabled: true`) | `server`, `email`, `api_token` / `api_token_env`, `jql`, `max_results`, `since` |
| Meeting transcripts | `meeting` | Opt-in (`enabled: true`) | `source_dirs`, `extensions`, `since` |

Every adapter accepts optional `since` (`YYYY-MM-DD` or `"all"`) — see [Sync lookback](#sync-lookback). Bare `llmwiki sync` runs every ingest-ready coding-agent adapter whose store is present and not explicitly disabled. Notes/export intake needs `enabled: true` (#326). Run `llmwiki configure-sources` to probe paths, set lookbacks, and write settings. Support map: [multi-agent-setup.md](multi-agent-setup.md).

Example:

```json
{
  "filters": {
    "since": "2026-07-31"
  },
  "adapters": {
    "copilot_chat": {
      "roots": ["/custom/path/to/vscode/workspaceStorage"]
    },
    "openclaw": {
      "since": "all"
    }
  }
}
```
