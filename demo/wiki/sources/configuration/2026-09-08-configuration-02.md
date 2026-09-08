---
title: "Configuration (part 2/3: Synthesis backend)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, synthesis-backend, lean-mode, incremental-synthesis, token-budget, downgrade-protection]
date: 2026-09-08
source_file: 
project: configuration
model: 
last_updated: 2026-09-08
---
## Summary

This part of the configuration guide defines how `llmwiki synth` chooses an LLM to write `wiki/sources/` pages via `synthesis.backend` in `config.json`, with nested per-engine settings and a one-run override via `--backend`. It contrasts synthesis backends (`dummy`, `ollama`, `claude`, `cursor_cli`) with session-ingest adapters, documents Claude and Cursor “lean” invocations for cost, incremental runs keyed off `llmwiki-state.json`, and downgrade protection so `dummy` stubs cannot replace real pages even under `--force`. It also notes removal of the legacy `agent` / `agent_delegate` flow in v1.4.0 and that vault root comes from `vault.default_path`, not `LLMWIKI_ROOT`.

## Key Claims

- `synthesis.backend` selects which engine (if any) generates wiki source pages; default when unset or invalid is `dummy`, with a warning on unknown values.
- `synthesis.backend: cursor_cli` drives page generation via the Cursor Agent CLI; contrib `cursor_cli` / `cursor_ide` adapters only ingest chats into `raw/` and are independent of the synthesis backend choice.
- Claude synthesis defaults to lean mode (no tool schemas, MCP, skills, `CLAUDE.md`, or full agent system prompt), described as roughly nine times cheaper per page than full invocations; Cursor lean uses ask mode, sandbox, and a truncated `--allowed-tools` list (~25–30% smaller prompt than full Composer tooling).
- Synthesis is incremental: `llmwiki-state.json` (`synth.files`) stores mtimes so only new or changed raw files are processed unless `--force` is used.
- Downgrade protection refuses to write stub (`dummy`) output over an existing non-stub page, including under `--force`; those files are reported as `protected`, and deliberate re-synthesis requires deleting the page first.
- An unavailable configured backend does not fall back to `dummy`; the run aborts with an error.
- The `agent` / `agent_delegate` pending-prompt backend was removed in v1.4.0; operators should use `claude` or `cursor_cli` instead.

## Key Quotes

> "Not the same as session ingest." — Clarifies that synthesis `cursor_cli` is the generator for wiki pages, not the chat-ingest adapter under the same name.

> "stub output is never written over a real page, even under `--force`" — States the downgrade-protection rule that prevents silent knowledge-graph collapse after misconfigured or default `dummy` runs.

> "That is ~9x cheaper per page, measured" — Anchors the default Claude lean-mode choice to documented synthesis cost reference material.

## Connections

- [[llmwiki]] (entity) — Product whose `synth` command and `config.json` `synthesis` block this document specifies.
  - fact: Resolves `synthesis.backend` and nested engine blocks; supports `--check`, `--estimate`, `--sessions-only`, and `--docs-only`.
- [[Wiki Synthesis]] (concept) — Automated pass from raw to `wiki/sources/` and related state; backend choice and incrementality define cost and behavior.
  - fact: Incremental processing is driven by per-file mtime in `<vault>/llmwiki-state.json`.
- [[Ollama]] (entity) — Local HTTP API backend option with `synthesis.ollama.{model,base_url,timeout,max_retries}`.
  - fact: Requires a running `ollama serve` instance.
- [[Cursor]] (entity) — `cursor_cli` synthesis uses `agent` / `cursor-agent` on `$PATH` with default model `composer-2.5`; distinct from Cursor ingest adapters.
- [[Claude Code]] (entity) — `claude` backend invokes synchronous `claude -p` with optional `synthesis.claude.path` and default model `sonnet`.
- [[CLAUDE.md]] (concept) — Stripped from Claude lean synthesis calls because stdout-only synthesis cannot use vault agent instructions.
- [[MCP Server]] (concept) — Omitted from lean Claude synthesis invocations alongside tools and skills for cost reduction.
