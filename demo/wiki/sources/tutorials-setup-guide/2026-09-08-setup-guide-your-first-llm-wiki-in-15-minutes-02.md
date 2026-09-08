---
title: "Setup Guide — Your First LLM Wiki in 15 Minutes (part 2/2: Part 4: Customization)"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-setup-guide, obsidian-integration, multi-agent-adapters, model-entities, command-palette-search, v1-2-export-migration]
date: 2026-09-08
source_file: 
project: tutorials-setup-guide
model: 
last_updated: 2026-09-08
---
## Summary

This installment finishes the “first LLM wiki in 15 minutes” tutorial with customization (project pages with topic chips, structured AI model entities and `/models/`, Obsidian vault linking, Cmd/Ctrl+K search filters, and build/sync exports) and a multi-agent section: core vs contrib adapters, optional meeting/Jira/web-clipper intake, portable wiki slash commands, and default session store paths per OS. It also notes v1.2.0 removals (`export-obsidian`, `export-qmd`, `export-marp`, and the old `pdf` adapter) with pointers to `UPGRADING.md` and related docs.

## Key Claims

- Project cards on the static site show topic chips when `wiki/projects/<slug>.md` includes a `topics` array (and related frontmatter such as `description` and `homepage`).
- Model entities with `entity_kind: ai-model` and structured `model` / `pricing` / `benchmarks` frontmatter are listed on a generated `/models/` page after `llmwiki build`.
- `llmwiki link-obsidian --vault <path>` symlinks the wiki into an Obsidian vault so graph view, backlinks, and Dataview on `wiki/dashboard.md` work against live `[[wikilinks]]`.
- Bare `llmwiki sync` runs only **core** adapters; contrib sources (e.g. `cursor_cli`, `openclaw`) require `llmwiki sync --adapter <name>`.
- Non-AI sources (meeting, Jira, web clipper) are enabled with `enabled: true` in sessions config, not via `--adapter`.
- `export-obsidian`, `export-qmd`, and `export-marp` were removed in v1.2.0; vault-oriented workflow uses `llmwiki sync --vault` plus `llmwiki build` for HTML and AI-oriented artifacts (`llms.txt`, `graph.jsonld`, etc.).

## Key Quotes

> "Rebuild and reload — the project card now shows topic chips." — documents the UX payoff of project frontmatter customization on the built site.

> "A bare `llmwiki sync` runs **core** adapters only. Contrib sources need `--adapter <name>`" — defines the default sync boundary vs optional agent backends.

> "The `export-obsidian`, `export-qmd`, and `export-marp` subcommands were removed in v1.2.0." — migration signal for readers on older docs or habits.

## Connections

- [[llmwiki]] (entity) — tutorial target product: project pages, model entities, build outputs, and sync/link commands.
  - fact: `llmwiki build` emits HTML plus `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, and `ai-readme.md`.
- [[Static Site]] (concept) — customization steps assume rebuild/reload of the generated site (project cards, `/models/`, Cmd+K palette).
- [[Obsidian]] (entity) — `link-obsidian` integration, vault sync, graph/backlinks/Dataview; detailed plugin setup deferred to `obsidian-integration.md`.
- [[Adapters]] (concept) — core vs contrib enablement, `--adapter` flag, and non-AI `enabled: true` sources.
- [[Claude Code]] (entity) — one of the supported agents; global slash commands copied to `~/.claude/commands/`.
- [[Codex CLI]] (entity) — core adapter; session path `~/.codex/sessions/` (and Windows equivalent).
- [[Cursor]] (entity) — contrib adapter (`cursor_cli`); workspaceStorage paths documented per OS.
- [[Gemini CLI]] (entity) — listed among agents that can feed one wiki when enabled.
- [[GitHub Copilot]] (entity) — Copilot Chat and Copilot CLI mentioned as additional session sources.
- [[Wikilinks]] (concept) — Obsidian graph and backlinks depend on `[[wikilink]]` usage across `wiki/`.
- [[Knowledge Graph]] (concept) — `graph.jsonld` from build relates to graph-oriented navigation and exports (alongside Obsidian graph view).
