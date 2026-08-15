---
title: "Command cheatsheet (part 2/2: All configurable settings (sessions_config.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, command-cheatsheet, configuration-reference, vault-architecture, cli-recipes, synthesis-backend]
date: 2026-08-10
source_file: 
project: command-cheatsheet
model: 
last_updated: 2026-08-11
---
## Summary

This documentation page provides a comprehensive reference for all configurable settings in `sessions_config.json`, covering vault layout, server configuration, graph engines, synthesis backends, and filtering options. It also documents the three-layer architecture (raw → wiki → site) that ensures immutable source data, and provides practical CLI recipes for common workflows including sync, serve, graph generation, and CI integration.

## Key Claims

- The default dev server port is 8765
- The default synthesis backend is `dummy` (not Ollama)
- The default model for Ollama synthesis is `llama3.1:8b`
- Sessions younger than 60 minutes are skipped by default
- Tool results are truncated to 500 characters by default
- The `raw/` directory is immutable and should never be modified
- The `site/` directory is generated and should not be edited by hand
- The vault layout uses four default subdirectories: `Wiki/Entities`, `Wiki/Concepts`, `Wiki/Sources`, `Wiki/Syntheses`

## Key Quotes

> "raw/     IMMUTABLE transcripts (source of truth, never modify)" — establishes the immutable, read-only nature of source data as the definitive record

> "llmwiki sync && llmwiki serve --open" — shows the recommended daily workflow combining synchronization with interactive development

> "wiki/    LLM-generated pages (you own this)" — clarifies that humans own and edit the wiki directory, distinguishing it from the read-only raw/ source directory

## Connections

- [[Obsidian]] and [[Logseq]] — vault systems supported for wiki export and integration
- [[Ollama]] — optional LLM backend for synthesis features

## Contradictions

None identified in this page.