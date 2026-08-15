---
title: "00 · Quickstart Walkthrough"
type: source
tags: [wiki-add, raw-doc, session-transcript, 00-quickstart-walkthrough, knowledge-graph, session-sync, obsidian-export, html-site]
date: 2026-08-10
source_file: 
project: 00-quickstart-walkthrough
model: 
last_updated: 2026-08-11
---
## Summary

This quickstart walks through the complete [[llm-wiki]] workflow in 10 steps: installing via pip, scaffolding a wiki structure with `/wiki-init`, syncing [[Claude Code]] and Codex CLI sessions, generating an AI-powered knowledge graph, building an HTML site with search and graph visualization, and exporting to [[Obsidian]]. The guide demonstrates how to discover and organize session transcripts into structured wiki content (sources, entities, concepts) and leverage automatic community detection to create interactive knowledge graphs and AI-consumable exports.

## Key Claims

- [[llm-wiki]] requires Python 3.12+ and [[Claude Code]]; installed via `pip install ".[graph]"` with graphify as an optional dependency
- `/wiki-init` creates 6 directory structures (raw/sessions, wiki/sources, wiki/entities, wiki/concepts, wiki/syntheses, site/) plus 8 seed files (index.md, overview.md, log.md, MEMORY.md, SOUL.md, CRITICAL_FACTS.md, hints.md, hot.md)
- `/wiki-sync` auto-discovers and converts ~487 [[Claude Code]] sessions and ~2 Codex CLI sessions into markdown by default
- AI-powered `/wiki-graph` (graphify) generates graphs with automatic community detection; typical output shows 1432 nodes, 875 edges, 871 communities, and 61 hyperedges attached
- The build process consolidates all exports into `llmwiki build`, producing HTML site, llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, and ai-readme.md
- [[Obsidian]] export requires prior graphify output (graphify-out/graph.json) and uses the Python API `export_to_obsidian()` from `llmwiki.graphify_bridge`

## Key Quotes

> "This walks through every feature using `/wiki-*` slash commands from [[Claude Code]]. Each step builds on the previous." — Establishes the pedagogical structure and the central role of IDE integration

> "A working wiki with knowledge graph, HTML site, Obsidian export, and AI-consumable outputs." — States the four core deliverables of the complete workflow

> "There is no separate `export` subcommand — replace `llmwiki export all` with `llmwiki build`." — Important API consolidation: build now produces all outputs (HTML, llms.txt, graph formats, etc.) instead of requiring a separate export step

## Connections

- [[llm-wiki]] — the entire system being documented; all features and workflows are specific to this tool
- [[Claude Code]] — the IDE environment where `/wiki-*` slash commands execute; primary discovery source for session transcripts
- [[Obsidian]] — target application for knowledge vault export; supports graph visualization via canvas and spatial layout
- [[Knowledge Graph]] — core feature generated via AI-powered graphify with automatic community detection and hyperedge attachment