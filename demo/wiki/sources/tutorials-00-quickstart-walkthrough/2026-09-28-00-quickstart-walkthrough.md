---
title: "00 · Quickstart Walkthrough"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-00-quickstart-walkthrough, installation, knowledge-graph, session-sync, automation]
date: 2026-09-28
source_file: 
project: tutorials-00-quickstart-walkthrough
model: 
last_updated: 2026-09-29
---
## Summary

This tutorial provides a 15-minute walkthrough of llm-wiki's complete feature set, from installation through production automation. It demonstrates the full loop: installing via pip, scaffolding a wiki with `/wiki-init`, syncing sessions from [[Claude Code]] and [[Codex CLI]] via [[Adapters]], generating knowledge graphs with graphify, building a browsable static HTML site, configuring daily automation, running quality checks with linting, querying via natural language, and exporting to both AI-consumable formats and [[Obsidian]].

## Key Claims

- Installation requires Python 3.12+ and `pip install ".[graph]"`; the version command reports 1.3.0 at time of writing.
- `/wiki-init` creates a standard directory structure with 9 seed files (`index.md`, `SOUL.md`, `CRITICAL_FACTS.md`, etc.), organized into `raw/sessions/`, `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`, and `site/`.
- `/wiki-sync` discovers Claude Code and Codex CLI sessions and ingests them using [[Adapters]]; the expected pipeline discovers hundreds of candidates but syncs only recent ones by default.
- Graphify AI-powered graph generation detects 1432 nodes, 875 edges, 871 communities, and attaches 61 hyperedges automatically when `/wiki-graph` runs.
- `/wiki-build` generates 1364+ HTML files (~200 MB) and multiple AI-consumable formats (llms.txt, llms-full.txt, graph.jsonld, rss.xml, robots.txt, sitemap.xml).
- `llmwiki install-automation` sets up a daily job with a configuration wizard; collection-only mode never contacts an AI provider, but synthesis mode does.
- `/wiki-lint` scans pages for broken [[Wikilinks]], orphan detection, duplicate detection, and frontmatter completeness; reports errors, warnings, and info-level issues.
- `/wiki-query` allows natural language questions about wiki content, returning synthesized answers with [[Wikilinks]] citations.
- `llmwiki export all` command was replaced by `llmwiki build`.
- Obsidian export is available via `graphify_bridge.export_to_obsidian()` and includes community pages (`_COMMUNITY_*.md`) and canvas layout (`graph.canvas`).

## Key Quotes

> **Time:** 15 minutes — establishes the entire tutorial as a half-hour-or-less onboarding loop

> "Each step builds on the previous." — reinforces the sequential, dependency-driven structure of the system

> "The site is plain files, nothing to start." — emphasizes that the output is a deployable static [[Static Site]] with no runtime dependencies

> "Collecting only never contacts an AI provider; summarising does." — clarifies cost/privacy implications of the two automation modes

> "There is no separate `export` subcommand — replace `llmwiki export all` with `llmwiki build`." — API change note indicating consolidation of build and export workflows

## Connections

- [[llmwiki]] (entity) — This tutorial is the primary onboarding path for the system; demonstrates all major features end-to-end.
  - fact: All steps (sync, graph, build, lint, query, export) are accessible via slash commands in [[Claude Code]].
  
- [[Wiki Synthesis]] (concept) — The tutorial describes session conversion into wiki summaries and knowledge structure.
  - fact: `/wiki-sync` converts Claude Code and Codex CLI sessions to markdown; `/wiki-graph` synthesizes them into a knowledge graph.

- [[Static Site]] (concept) — The site generation and browsing loop is step 5–6.
  - fact: `/wiki-build` outputs 1364+ HTML files; the site has home, projects, sessions, graph, docs, and search views.

- [[Knowledge Graph]] (concept) — Graphify is the core of step 4.
  - fact: Graphify detects communities and hyperedges, outputting JSON, HTML, SVG, and a report.

- [[Adapters]] (entity) — Session sync relies on two built-in adapters.
  - fact: `claude_code` and `codex_cli` adapters discover and ingest sessions via the `/wiki-sync` workflow.

  - fact: `/wiki-sync` adapter discovers Claude Code sessions; 12 were synced in the example output.

- [[Codex CLI]] (entity) — Sessions sourced from Codex CLI history.
  - fact: `/wiki-sync` adapter discovers Codex CLI sessions; 2 were synced in the example output.

- [[Obsidian]] (entity) — Export target for graph data.
  - fact: `graphify_bridge.export_to_obsidian()` writes community pages and a canvas file to an Obsidian vault; press **Cmd+G** for graph view.

- [[Wikilinks]] (concept) — Core linking mechanism throughout the system.
  - fact: `/wiki-query` returns answers with [[wikilink]] citations; `/wiki-lint` validates link integrity.

- [[GitHub Actions]] (entity) — Automated daily workflows setup.
  - fact: `llmwiki install-automation` configures daily collection and synthesis jobs with optional quality checks and custom schedules.

- [[Lint Rules]] (concept) — Quality assurance step 8.
  - fact: `/wiki-lint` checks `link_integrity`, `orphan_detection`, `duplicate_detection`, and `frontmatter_completeness`; reports 2358 issues (1 error, 1187 warnings, 1170 info) in the example.