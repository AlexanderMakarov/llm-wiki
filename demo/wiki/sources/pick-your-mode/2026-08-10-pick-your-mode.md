---
title: "Pick your mode"
type: source
tags: [wiki-add, raw-doc, session-transcript, pick-your-mode, synthesis-backends, workflow-integration, configuration, ollama]
date: 2026-08-10
source_file: 
project: pick-your-mode
model: 
last_updated: 2026-09-07
---
## Summary

llmwiki offers three interchangeable synthesis backends—**Ollama** (local HTTP), **Claude CLI** (command-line interface), and **Dummy** (offline stubs)—that differ only in who calls the LLM, while sharing identical adapters, static site generation, graph viewer, and lint rules. Users select a backend via the `synthesis.backend` configuration key, enabling them to choose between daily Claude Code integration, fully local/air-gapped operation, or offline evaluation.

## Key Claims

- Three synthesis backends (Ollama, Claude CLI, Dummy) all use the same three-layer pipeline (`raw/` → `wiki/` → `site/`) but differ only in synthesis execution strategy
- Claude CLI backend integrates with Claude Code daily workflows and requires no external API key
- Ollama backend enables fully local and air-gapped synthesis without external API calls
- Dummy backend is designed for tests and dry previews and performs no actual synthesis
- All backends share identical implementations of adapters, static site generation, graph viewer, and lint rules
- Agent-delegate pending-prompt mode (`--list-pending` / `--complete`) was removed in v1.4.0
- Anthropic HTTP batch and API-mode scaffolding was removed in favor of `claude` or `ollama` backends

## Key Quotes

> "llmwiki synthesis backends share the same three-layer pipeline (`raw/` → `wiki/` → `site/`) but differ on *who calls the LLM*" — Synthesis backends are pluggable execution strategies at one layer of a standardized multi-layer pipeline

> "Everything except synthesis" — Backend choice is isolated to the synthesis layer; adapters, static site generation, and other infrastructure remain backend-agnostic

## Connections

- [[llmwiki]] (system) — documents the architecture of the synthesis backend system and provides a decision framework for backend selection
- [[Claude Code]] (tool) — one of two production backends; integrates with Claude Code daily agent workflow
- [[Ollama]] (tool) — one of two production backends; enables fully local, air-gapped synthesis
- [[Adapters]] (concept) — work identically across all backends; backend choice does not affect adapter behavior
- [[Configuration]] (concept) — backend selection controlled via the `synthesis.backend` key in config.json
  - fact: Valid values are `claude`, `ollama`, or `dummy`
- [[Static Site]] (output) — all backends produce identical static site output
- [[Knowledge Graph]] (feature) — graph viewer visualization is backend-agnostic across all synthesis modes