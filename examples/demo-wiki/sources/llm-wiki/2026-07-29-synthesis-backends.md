---
title: "Synthesis backends"
type: source
tags: [raw-doc, demo, llmwiki, synthesis, session-transcript, llm-wiki, backend-configuration, cost-estimation, local-models]
date: 2026-07-29
source_file: raw/docs/llm-wiki/synthesis-backends.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

This documentation describes the synthesis backend system in llm-wiki, which determines how wiki source pages are generated. Three backends are available: `dummy` for offline CI scaffolding, `ollama` for local models, and `claude` for Claude Code CLI usage. The page includes practical tips for cost-effective synthesis, including model selection, cost estimation before runs, and state isolation for demo vaults.

## Key Claims

- `synthesis.backend` in `config.json` (overlaying `examples/sessions_config.json`) determines how wiki source pages are generated
- Three backends exist: `dummy` (offline scaffolding), `ollama` (local), and `claude` (cloud default)
- Claude is the default quality path for maintainers
- Haiku is recommended as a cost-effective model for documentation with lean prompts
- `--docs-only` flag skips the session backlog when only documents are modified
- `--estimate` flag shows token and dollar cost before running a full synthesis
- `--vault <path>` isolates synthesis state to prevent sharing idempotency tracking with personal Obsidian vaults

## Key Quotes

> "Prefer a cheap model for docs (`haiku`) and lean prompts (`claude_lean: true`)." — Cost-effective model selection strategy for documentation synthesis

> "`llmwiki synthesize --docs-only` skips session backlog when you only added documents." — Workflow optimization for documentation-only updates

## Connections

- [[llm-wiki]] — the project these synthesis backends serve
- [[synthesis]] — the pipeline stage this page configures
- [[Ollama]] — local backend option for offline synthesis
- [[Claude]] — cloud backend powered by Anthropic
- [[Karpathy]] — knowledge-base shape the backends write toward
- [[MCP]] — editors often trigger synthesis-adjacent reads via MCP tools

## Contradictions

None identified (early in wiki development).