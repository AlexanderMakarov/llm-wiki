---
title: "Cursor adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, cursor-adapter, workspace-discovery, cross-platform-paths, schema-versioning, jsonl-parsing]
date: 2026-08-10
source_file: 
project: cursor-adapter
model: 
last_updated: 2026-08-11
---
## Summary

This page documents the Cursor adapter (v0.5, production) for [[llmwiki]], which ingests conversation history from Cursor IDE workspaces. The adapter discovers workspace directories across macOS, Linux, and Windows platforms, derives project slugs by truncating and prefixing workspace hashes, and currently supports v1 schema JSONL files. Future versions will extract friendly workspace names from `workspace.json` metadata instead of relying on opaque hash identifiers.

## Key Claims

- Cursor workspace storage uses platform-specific paths: `~/Library/Application Support/Cursor/` (macOS), `~/.config/Cursor/` (Linux), and `%APPDATA%\Cursor\` (Windows)
- Workspace hashes are truncated to 12 characters and prefixed with `cursor-` to generate project slugs (e.g., `cursor-a1b2c3d4e5f6` from `workspaceStorage/a1b2c3d4e5f6789/`)
- Only v1 schema is currently supported for JSONL conversation files
- Configuration can override default search roots via `config.json` with adapter-specific settings
- A synthetic test fixture exists at `tests/fixtures/cursor/minimal.jsonl` for converter round-trip testing

## Key Quotes

> "Future versions will read `workspace.json` from each workspace directory to extract the friendly project name."

This indicates a planned refinement to replace hash-based slugs with human-readable workspace identifiers.

## Connections

- [[Adapter Architecture]] — documents a concrete adapter implementation following the llmwiki plugin pattern
- [[llmwiki]] — the parent project providing adapter infrastructure and conventions

## Contradictions

None identified.