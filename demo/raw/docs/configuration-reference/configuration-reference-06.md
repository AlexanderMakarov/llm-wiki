---
title: "Configuration Reference (part 6/8)"
slug: configuration-reference-06
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 6 of 8 of **Configuration Reference**.

| false | Opt-in; requires explicit `conversations_json` |
| `chatgpt` | `conversations_json` | string | — | Path to export file |
| `web_clipper` | `enabled` | bool | false | Obsidian Web Clipper intake path |
| `web_clipper` | `watch_dir` | string | `"raw/web"` | Directory to watch |
| `web_clipper` | `extensions` | list | `[".md"]` | File extensions to pick up |
| `web_clipper` | `auto_queue` | bool | true | Auto-enqueue into unified `llmwiki-state.json` queue |
| `site` | `github_repo` | string | `""` | Optional `owner/name` for CHANGELOG / edit-on-GitHub / source-code links in compiled docs. Empty = detect from `git remote get-url origin`, else `Pratiyush/llm-wiki` |
