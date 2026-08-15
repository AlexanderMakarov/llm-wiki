---
title: "Obsidian Integration Guide"
type: source
tags: [wiki-add, raw-doc, session-transcript, obsidian-integration-guide, dataview, wikilinks, two-way-editing]
date: 2026-08-10
source_file: 
project: obsidian-integration-guide
model: 
last_updated: 2026-08-11
---
## Summary

This guide explains how to integrate llmwiki into Obsidian via two simple setup methods (standalone vault or symlink) and recommends five core plugins, with Dataview being essential for dashboards and queries. The design preserves user edits outside managed sections across ingestions, enabling bidirectional editing workflows while maintaining consistency through tools like Obsidian Linter and Web Clipper for article ingestion.

## Key Claims

- llmwiki outputs plain markdown with YAML frontmatter and `[[wikilinks]]` that Obsidian reads natively, providing immediate access to graph view, backlinks, and full-text search
- Dataview plugin is required for `wiki/dashboard.md` and category page functionality to work
- Two setup methods are supported: opening `wiki/` as a standalone Obsidian vault, or symlinking into an existing vault via `llmwiki link-obsidian` CLI command
- Obsidian's ingest pipeline preserves user edits in sections outside frontmatter and managed sections (e.g., custom `## Notes` or `## Follow-ups`), guaranteeing safe bidirectional editing
- Web Clipper can be configured to auto-queue articles saved to `raw/web/` for automatic ingestion into the wiki
- Graph view can be styled with semantic color groups: entities (blue), concepts (green), sources (amber), syntheses (purple)

## Key Quotes

> "llmwiki emits plain markdown with YAML frontmatter and `[[wikilinks]]` — exactly what Obsidian reads natively" — Defines the core design principle enabling seamless integration

> "Obsidian edits directly to `wiki/*.md` are preserved — llmwiki's ingest pipeline never overwrites sections outside the frontmatter and the specific sections it manages" — Establishes the safety guarantee for bidirectional editing

## Connections

- [[Obsidian]] — the host application providing native markdown rendering, graph visualization, and backlinks
- [[Dataview]] — required plugin for executing live YAML-based queries across frontmatter metadata
- [[Wikilinks]] — markdown link syntax that Obsidian renders natively for bidirectional linking and graph construction
- [[Templater]] — enables keyboard-driven creation of new wiki pages from template files in `examples/obsidian-templates/`
- [[Web Clipper]] — browser extension for capturing web articles directly into `raw/web/` for automated ingestion

## Contradictions

None identified.