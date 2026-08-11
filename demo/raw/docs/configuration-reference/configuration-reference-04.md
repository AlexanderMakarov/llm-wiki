---
title: "Configuration Reference (part 4/4: Environment variables)"
slug: configuration-reference-04
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/configuration-reference.md"
content_sha256: 7cc907826ce49fb66b474eaa7bcf6d0d7266d2ba89c92ce2acdfe2a0f97b84f5
---

> Part 4 of 4 of **Configuration Reference** — Environment variables.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLMWIKI_CONFIG` | Override the config file path | `./config.json`, then `examples/sessions_config.json` |
| `COPILOT_HOME` | Override the Copilot CLI base directory | `~/.copilot` |

Vault content root is **`vault.default_path` in `config.json`**. The removed `LLMWIKI_ROOT` env var is no longer read.

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

| Adapter | Config key | AI session? | Configurable fields |
|---|---|---|---|
| Claude Code | `claude_code` | yes (default on) | `roots` |
| Codex CLI | `codex_cli` | yes (default on) | `roots` |
| Copilot Chat | `copilot_chat` | yes (default on) | `roots` |
| Copilot CLI | `copilot_cli` | yes (default on) | `roots` |
| Cursor | `cursor` | yes (default on) | `roots` |
| Gemini CLI | `gemini_cli` | yes (default on) | `roots` |
| OpenCode / OpenClaw (app-config dir) | `opencode` | yes (default on) | `roots` |
| OpenClaw (native session store) | `openclaw` | yes (default on) | `roots` |
| ChatGPT | `chatgpt` | yes (opt-in) | `enabled`, `conversations_json` |
| Obsidian | `obsidian` | **no** (opt-in) | `vault_paths`, `exclude_folders`, `min_content_chars` |
| Jira | `jira` | **no** (opt-in) | `server`, `email`, `api_token` / `api_token_env`, `jql`, `max_results` |
| Meeting transcripts | `meeting` | **no** (opt-in) | `source_dirs`, `extensions` |

Non-AI-session adapters are opt-in only (#326) — set `{name}.enabled: true` in this config to have them fire on `sync`.

Example:

```json
{
  "adapters": {
    "copilot_chat": {
      "roots": ["/custom/path/to/vscode/workspaceStorage"]
    }
  }
}
```
