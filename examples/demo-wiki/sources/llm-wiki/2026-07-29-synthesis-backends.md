---
title: "Synthesis backends"
type: source
tags: [raw-doc, demo, llmwiki, synthesis, session-transcript, llm-wiki, model-selection, cost-optimization, offline-ci, claude-cli]
date: 2026-07-29
source_file: raw/docs/llm-wiki/synthesis-backends.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

Documents three synthesis backends for filling wiki pages in llm-wiki: `dummy` for offline CI/scaffolding, `ollama` for local models, and `claude` as the default quality path for maintainers. Provides cost optimization guidance for Claude synthesis, including using Haiku model, lean prompts, and CLI flags like `--docs-only` and `--estimate` to preview costs.

## Key Claims

- Three synthesis backends are available: `dummy` (offline/scaffolding), `ollama` (local models), and `claude` (Claude Code CLI, default quality)
- Haiku is recommended as a cost-effective model for documentation synthesis
- The `--docs-only` flag skips session backlog when only documents are added
- The `--estimate` flag previews token count and cost before running synthesis
- The `--vault <path>` flag isolates synthesis state to prevent demo/staging vaults from affecting production idempotency

## Key Quotes

> "Prefer a cheap model for docs (`haiku`) and lean prompts (`claude_lean: true`)." — Cost optimization strategy for Claude synthesis

> "Claude Code CLI (`claude -p`) — default quality path for maintainers" — Designation of Claude as the recommended backend

## Connections

- [[llm-wiki]] — the project implementing these synthesis backends
- [[Ollama]] — alternative open-source backend for local model synthesis
- [[Claude Code CLI]] — the tool implementing the Claude synthesis backend