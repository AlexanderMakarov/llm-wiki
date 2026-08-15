---
title: "Command cheatsheet (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, command-cheatsheet, cli-reference, slash-commands, knowledge-graph, quick-start, adapters]
date: 2026-08-10
source_file: 
project: command-cheatsheet
model: 
last_updated: 2026-08-11
---
## Summary

This is raw documentation (part 1 of 2) serving as a comprehensive reference for [[llmwiki]] commands and workflows. It covers 12 core CLI commands, slash command equivalents, knowledge graph operations (including AI-powered Graphify support), adapter integrations, and configuration patterns.

## Key Claims

- llmwiki provides dual interfaces: slash commands (for Claude Code/Codex CLI contexts) and terminal CLI commands
- The system includes 12 core commands: init, sync, build, serve, adapters, graph, query, all, lint, candidates, synth, and version
- Knowledge graphs can be built with a builtin wikilink approach or AI-powered Graphify engine (tree-sitter AST extraction, semantic analysis, community detection)
- Core adapters (claude_code, codex_cli) are auto-discovered; 7 contrib adapters (chatgpt, copilot_chat, copilot_cli, cursor, gemini_cli, obsidian, opencode) are available on-demand
- Obsidian vaults can be used as external storage via `--vault` flag
- Wiki quality is enforced via 17 structural rules in the lint command

## Key Quotes

> "Everything you need on one page. Slash commands work inside Claude Code / Codex CLI; CLI commands run at your terminal." — Establishes the dual-interface philosophy: users can choose between slash commands in AI editors or CLI commands in their terminal.

## Connections

- [[llmwiki]] — the core system this cheatsheet documents