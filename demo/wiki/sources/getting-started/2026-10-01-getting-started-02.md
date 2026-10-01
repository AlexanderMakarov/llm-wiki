---
title: "Getting started (part 2/2: Three commands after install)"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, cli-workflow, vault-structure, mcp-integration, multi-agent-support, web-ui]
date: 2026-10-01
source_file: 
project: getting-started
model: 
last_updated: 2026-10-01
---
## Summary

This is the second part of the getting-started guide, covering the three core commands users run after installation (`sync`, `synth`, `build`), the `llmwiki add` command for ingesting non-session documents, the optional automation wizard, the vault directory structure and data isolation, web UI keyboard shortcuts, MCP integration for agents, multi-agent support, and wiki synthesis via Claude Code with the `/wiki-ingest` command.

## Key Claims

- The three core post-install commands are `llmwiki sync` (pull sessions), `llmwiki synth` (synthesize wiki), and `llmwiki build` (compile to HTML), which can be combined via `llmwiki all`.
- `llmwiki add` supports markdown files, web pages, PDFs, and folders as first-class document types, with optional `--synthesize` flag to generate wiki source pages.
- All vault data is stored outside the git clone (configured via `vault.default_path`) in separate directories for raw sessions, wiki pages, and generated HTML; none of it is committed.
- The web UI provides keyboard shortcuts (⌘K/Ctrl+K for command palette, `/` for search, `g h`/`g p`/`g s` for navigation) for browsing the wiki.
- Multi-agent support allows simultaneous session syncing from Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI, with colored badges per agent.
- The `llmwiki install-automation` wizard sets up daily jobs to automatically collect sessions and optionally synthesize them into wiki pages.

## Key Quotes

> `llmwiki all` runs all three in one go, then builds the graph and reports quality findings. — Summarizing the unified command for the complete workflow.

> Session sync is the default path, but notes and external sources are first-class too. — Clarifying that non-session documents have equal status in the wiki.

> The vault lives outside the repo, so it is never committed and never sent anywhere. — Emphasizing data isolation and privacy by design.

> The agent reads the source markdowns from the vault, writes summary pages, cross-links entities, and updates `wiki/index.md`. — Explaining what the `/wiki-ingest` command does inside Claude Code to synthesize wiki pages.

## Connections

- [[llmwiki]] (entity) — the core system for which this is a getting-started guide
  - fact: After installation, users run three commands in sequence: `sync` (pull sessions), `synth` (fill wiki pages), and `build` (compile to HTML).
- [[Wiki Synthesis]] (concept) — the `synth` step that fills wiki source pages from raw markdown
  - fact: `llmwiki synth` fills `wiki/sources/` and harvests `wiki/candidates/` for review before merging into the published wiki.
- [[Static Site]] (concept) — the generated HTML output accessible via web UI after `build`
  - fact: The static site at `<vault>/site/index.html` provides keyboard shortcuts (⌘K, `/`, `g h`) and navigation for browsing wiki content.
- [[MCP Server]] (entity) — integration point for agents to access wiki tools like `wiki_search` and `wiki_read_page`
  - fact: MCP clients are configured to point at `python3 -m llmwiki.mcp` to access wiki tools that query the same vault.
- [[Claude Code]] (entity) — used to synthesize wiki pages via the `/wiki-ingest` command
  - fact: Running `/wiki-ingest raw/sessions/<project>/` inside Claude Code reads raw markdown and writes summary pages with cross-links and entity updates.
- [[Adapters]] (concept) — multi-agent sync support from six different agents simultaneously
  - fact: Sessions from Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI can be synced at the same time, each with a colored badge showing its source agent.

## Contradictions

None identified.