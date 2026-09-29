---
title: "Configuration Reference (part 6/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, mcp-tool-timeouts, jira-adapter, web-clipper-adapter]
date: 2026-09-28
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-28
---
## Summary

This documentation page (part 6 of 8 of the Configuration Reference) comprehensively catalogs configuration parameters for major [[llmwiki]] integrations including [[Adapters]] for JIRA (with email/API token authentication and JQL query support), ChatGPT (via conversations export), [[Obsidian]] Web Clipper (with directory watching and auto-queueing), GitHub repository detection for site settings, and [[MCP Server]] tool timeout budgets.

## Key Claims

- JIRA adapter supports JQL queries for ticket filtering and configurable pagination (default 50 results) via `jira.jql` and `jira.max_results`
- ChatGPT integration is opt-in (disabled by default) and requires an explicit `conversations_json` export file path
- Obsidian Web Clipper watches the `raw/web/` directory by default and auto-enqueues markdown files into the unified `llmwiki-state.json` queue
- Site `github_repo` setting auto-detects from `git remote get-url origin` or defaults to `AlexanderMakarov/llm-wiki` if not specified; empty value enables auto-detection
- MCP tool timeouts default to 120 seconds per tool (both `wiki_add` and `wiki_sync`) and support per-tool overrides via configuration

## Key Quotes

> "Per-tool wall-clock budgets (seconds) for long-running MCP tools. Missing keys use 120."

— Clarifies MCP tool timeout behavior with sensible defaults and optional per-tool customization.

> "Optional `owner/name` for CHANGELOG / edit-on-GitHub / source-code links in compiled docs. Empty = detect from `git remote get-url origin`, else `AlexanderMakarov/llm-wiki`"

— Documents the flexible GitHub repository detection strategy for site generation features.

## Connections

- [[llmwiki]] (entity) — the main project whose integrations are configured
  - fact: Supports configuration for JIRA, ChatGPT, Web Clipper, site, and MCP tool parameters.

- [[Adapters]] (entity) — JIRA, ChatGPT, and Web Clipper are integration adapters
  - fact: Each adapter has independent configuration sections for authentication, file paths, and behavior (e.g., JQL filtering, auto-queueing).

- [[Obsidian]] (entity) — Web Clipper is an Obsidian extension for llmwiki ingestion
  - fact: Web Clipper watches `raw/web/` by default and auto-enqueues `.md` files into the unified intake queue.

- [[MCP Server]] (entity) — tool timeout configuration for Model Context Protocol operations
  - fact: Configurable per-tool wall-clock budgets (default 120 seconds) for `wiki_add` (synthesis pipeline) and `wiki_sync` (synchronization).

- [[GitHub Pages]] (entity) — `github_repo` setting drives site-generated GitHub-related links
  - fact: Supports auto-detection from git remote or manual specification for CHANGELOG, edit-on-GitHub, and source-code links.

- [[Wiki Synthesis]] (concept) — `wiki_add` timeout encompasses content conversion through site building
  - fact: The 120-second default timeout for `wiki_add` covers convert, optional synthesis, and site compilation stages.

## Contradictions

None identified.