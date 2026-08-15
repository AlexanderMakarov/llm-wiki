---
title: "GitHub Copilot adapters"
type: source
tags: [wiki-add, raw-doc, session-transcript, github-copilot-adapters, adapter-configuration, workspace-storage, cli-sessions]
date: 2026-08-10
source_file: 
project: github-copilot-adapters
model: 
last_updated: 2026-08-11
---
## Summary

llmwiki ships two production-ready adapters (v0.6) for [[GitHub Copilot]], solving the integration challenge of two completely different storage layouts. Copilot Chat (VS Code extension) stores workspace-scoped conversations in `workspaceStorage` across 9 platform/editor combinations and uses truncated workspace hashes for project slugs; Copilot CLI stores session logs in `~/.copilot/session-state` and uses session-ids directly. Both support schema v1 and allow configuration override via config.json and the `COPILOT_HOME` environment variable.

## Key Claims

- Copilot Chat adapter auto-discovers 9 default roots (3 platforms × 3 editor variants: VS Code, Code-Insiders, VSCodium) and derives project slugs by truncating opaque workspace hashes to 12 characters with a `copilot-` prefix.
- Copilot CLI adapter reads from `~/.copilot/session-state/<session-id>/events.jsonl` and uses the session-id directory name directly as the project slug, without transformation.
- Both adapters maintain canonical registry names (`copilot_chat`, `copilot_cli`) and back-compat aliases (`copilot-chat`, `copilot-cli`) to support existing configurations, per issue #626.
- Copilot CLI adapter respects the `COPILOT_HOME` environment variable, automatically adding `$COPILOT_HOME/session-state/` as an additional root when set.
- Both adapters are Production status (v0.6) and support only schema version v1.

## Key Quotes

> "The GitHub Copilot Chat extension for VS Code stores per-workspace conversation files under the editor's `workspaceStorage` directory" — establishes the Chat adapter's data source and the opaque hash challenge that drove the 12-character truncation slug design.

> "Uses the session-id directory name directly" (CLI) — contrasts with Chat's hash-truncation approach, showing how different Copilot products' storage layouts mandate different slug derivation strategies.

> "The adapter also checks the `COPILOT_HOME` environment variable. When set, it adds `$COPILOT_HOME/session-state/` as an additional root." — enables CLI flexibility for non-standard home directory configurations without requiring config.json edits.

## Connections

- [[GitHub Copilot]] — the product being integrated
- [[llmwiki]] — the project shipping these adapters

## Contradictions

None identified. Chat and CLI adapters' different slug derivation strategies (12-char hash truncation vs. direct session-id) are intentional and complementary, reflecting their respective Copilot products' distinct storage schemas.