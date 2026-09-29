---
title: "Configuration (part 2/3: Synthesis backend)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, synthesis-backend, lean-mode, cost-optimization, state-tracking]
date: 2026-09-28
source_file: 
project: configuration
model: 
last_updated: 2026-09-28
---
## Summary

This documentation section details the synthesis backend configuration system that transforms raw sessions and documents into wiki source pages. It describes four available backends (dummy for testing, ollama for local LLMs, claude for synchronous CLI calls, and cursor_cli for Cursor Agent CLI), their settings in `config.json`, lean mode cost optimization (~9× cheaper for Claude), incremental synthesis via state tracking, and safety features like downgrade protection.

## Key Claims

- The `synthesis.backend` key in `config.json` determines which LLM (if any) synthesizes sessions/documents into wiki pages; can be overridden per-run with `--backend` without modifying the config file.
- Claude synthesis runs in lean mode by default, stripping tool schemas, MCP servers, skills, `CLAUDE.md`, and system prompts from each invocation, reducing cost ~9× since synthesis only reads stdout.
- Cursor Agent CLI lean mode applies specific flags (`-p`, `--mode ask`, `--sandbox enabled`, `--allowed-tools truncated_tool_call`) to achieve similar cost reduction (~25–30% less prompt than full tool catalog).
- Synthesis is incremental: `llmwiki-state.json` tracks mtimes per raw file; nightly `sync`/`synthesize` only processes new or changed files, making daily LLM costs proportional to new content rather than corpus size.
- Downgrade protection prevents the dummy backend from overwriting real synthesized pages with stub pages, even with `--force` — pages are marked `protected` in the summary, and users must delete a real page first to re-synthesize it.
- Claude defaults to the `sonnet` model (rather than cheaper alternatives) based on measured cost-effectiveness per page.
- Synthesis backends (generator LLMs) are distinct from ingest adapters: configuring `synthesis.backend: cursor_cli` does not select the `cursor_cli` or `cursor_ide` adapters.

## Key Quotes

> "Claude calls run in **lean mode** by default: tool schemas, MCP servers, skills, `CLAUDE.md`, and the agent system prompt are stripped from each invocation, since a synthesis call only reads stdout and can't use any of them. That is ~9x cheaper per page, measured"

This establishes lean mode as a core cost optimization, explaining why it is the default for Claude synthesis.

> "**Synthesis is incremental.** `<vault>/llmwiki-state.json` (`synth.files`) records an mtime per raw file; a nightly `sync`/`synthesize` only processes files that are new or changed since the last run — the daily LLM bill is proportional to new content, not to corpus size."

Demonstrates how state tracking enables cost-proportional growth even as the knowledge base expands.

> "The pipeline now refuses that downgrade: stub output is never written over a real page, even under `--force` — such pages are reported as `protected` in the run summary."

Shows the safety mechanism preventing accidental data loss from downgrading a real synthesized page to a dummy stub.

## Connections

- [[llmwiki]] (entity) — configuration system that selects which backend LLM synthesizes wiki pages
  - fact: `synthesis.backend` in `config.json` determines the LLM/tool used to generate wiki source pages
  - fact: incremental synthesis via `llmwiki-state.json` state tracking keeps daily LLM costs proportional to new content

- [[Wiki Synthesis]] (concept) — this documentation details backend selection, configuration, lean mode, and incremental state tracking for synthesis
  - fact: four backends available: dummy (stub pages), ollama (local LLM), claude (sync CLI), cursor_cli (Cursor Agent CLI)
  - fact: lean mode ~9× cheaper for Claude by stripping context not needed for reading stdout

- [[MCP Server]] (entity) — lean mode strips MCP servers from Claude synthesis to reduce cost
  - fact: MCP servers are removed from lean mode invocations since synthesis only reads stdout

- [[Ollama]] (entity) — local LLM backend option via HTTP API
  - fact: Ollama backend requires running `ollama serve` and configurable via `synthesis.ollama.{model,base_url,timeout,max_retries}`

- [[Cursor]] (entity) — Cursor Agent CLI (`agent` or `cursor-agent` binary) used as synthesis backend
  - fact: `cursor_cli` backend applies lean flags (`-p`, `--mode ask`, `--sandbox enabled`, `--allowed-tools truncated_tool_call`) for cost reduction

- [[Adapters]] (entity) — synthesis backends are distinct from ingest adapters despite name overlap
  - fact: `synthesis.backend: cursor_cli` (generator) differs from `cursor_cli` (Agent CLI chat ingester) and `cursor_ide` (IDE Composer ingester) contrib adapters