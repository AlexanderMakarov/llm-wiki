---
title: "Configuration Reference (part 6/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, web-clipper, chatgpt-export, sessions-config, github-repo, site-metadata]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
## Summary

Part 6 of the configuration reference documents opt-in intake for ChatGPT (`conversations_json` export path), the Obsidian Web Clipper watcher (`watch_dir`, extensions, unified queue via `llmwiki-state.json`), and `site.github_repo` for CHANGELOG, edit-on-GitHub, and source links in built docs—with detection from `git remote` and a documented fallback when unset.

## Key Claims

- The ChatGPT source is opt-in and only applies when `conversations_json` points at an export file path.
- Web Clipper defaults to off (`enabled: false`), watches `"raw/web"`, accepts `[".md"]`, and with `auto_queue: true` enqueues picked-up files into the unified `llmwiki-state.json` queue.
- `site.github_repo` is optional `owner/name`; when empty, llmwiki resolves from `git remote get-url origin`, otherwise falls back to `Pratiyush/llm-wiki` for CHANGELOG and GitHub-facing links in compiled output.

## Key Quotes

> "Opt-in; requires explicit `conversations_json`" — documents that ChatGPT intake is not enabled by default.

> "Auto-enqueue into unified `llmwiki-state.json` queue" — ties Web Clipper file pickup to the same processing queue as other sources.

> "Empty = detect from `git remote get-url origin`, else `Pratiyush/llm-wiki`" — defines resolution order for repo metadata on the static site.

## Connections

- [[llmwiki]] (entity) — these keys live in the product configuration surface (sessions, clipper, site).
  - fact: Web Clipper `auto_queue` feeds the unified `llmwiki-state.json` queue.
- [[Obsidian]] (entity) — `web_clipper` is the Obsidian Web Clipper intake path into `raw/web`.
- [[Static Site]] (concept) — `site.github_repo` drives CHANGELOG, edit-on-GitHub, and source-code links in compiled docs.
- [[Adapters]] (concept) — `chatgpt` / `conversations_json` is an explicit opt-in conversation source alongside core session adapters.
