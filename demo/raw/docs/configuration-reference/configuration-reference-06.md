---
title: "Configuration Reference (part 6/8)"
slug: configuration-reference-06
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/configuration-reference.md"
content_sha256: a94f88e12736fb1eb7ca6bf1d509cef2af5bfc5ca59c974abbe8c0cbb274a294
---

> Part 6 of 8 of **Configuration Reference**.

d/Server URL |
| `jira` | `email` | string | — | Account email |
| `jira` | `api_token` | string | `""` | Prefer `api_token_env` + `.env` |
| `jira` | `jql` | string | sensible default | Query for tickets to sync |
| `jira` | `max_results` | int | 50 | Pagination cap |
| `chatgpt` | `enabled` | bool | false | Opt-in; requires explicit `conversations_json` |
| `chatgpt` | `conversations_json` | string | — | Path to export file |
| `web_clipper` | `enabled` | bool | false | Obsidian Web Clipper intake path |
| `web_clipper` | `watch_dir` | string | `"raw/web"` | Directory to watch |
| `web_clipper` | `extensions` | list | `[".md"]` | File extensions to pick up |
| `web_clipper` | `auto_queue` | bool | true | Auto-enqueue into unified `llmwiki-state.json` queue |
| `site` | `github_repo` | string | `""` | Optional `owner/name` for CHANGELOG / edit-on-GitHub / source-code links in compiled docs. Empty = detect from `git remote get-url origin`, else `AlexanderMakarov/llm-wiki` |
| `mcp` | `tool_timeouts` | object | see keys | Per-tool wall-clock budgets (seconds) for long-running MCP tools. Missing keys use 120. See [mcp.md § Tool timeouts](reference/mcp.md#tool-timeouts). |
| `mcp.tool_timeouts` | `wiki_add` | number (s) | 120 | Timeout for MCP `wiki_add` (convert + optional synth + site build) |
| `mcp.tool_timeouts` | `wiki_sync` | number (s) | 120 | Timeout for MCP `wiki_sync` subprocess |
