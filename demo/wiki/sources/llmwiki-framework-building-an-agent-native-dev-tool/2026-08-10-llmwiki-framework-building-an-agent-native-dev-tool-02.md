---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 2/3: Phase 3 — Structure)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-framework-building-an-agent-native-dev-tool, adapter-contribution, privacy-first, schema-versioning, performance-budgets]
date: 2026-08-10
source_file: 
project: llmwiki-framework-building-an-agent-native-dev-tool
model: 
last_updated: 2026-08-11
---
## Summary

This session documents the architectural specification for [[llmwiki]] (Phases 3–6 of the framework build plan). Phase 3 specifies a single-package structure with adapters and templates as subdirectories. Phase 4 enforces cross-cutting rules: CSS/JS embedded as Python constants for single-file rendering, performance budgets (cold build < 15s, site < 50 MB, per-session HTML < 500 KB), privacy-first defaults (redaction before storage, no telemetry, local-only binding), and schema-versioning for graceful adapter degradation. Phase 5.25 (NEW) introduces a standardized adapter contribution contract requiring exactly seven artifacts (adapter code, fixture, snapshot test, unit test, documentation page, changelog entry, README mention) that will be enforced by GitHub Actions CI. Phases 5.5–6 detail pre-launch QA checklist and release procedures.

## Key Claims

- There is exactly one `llmwiki/` Python package; tools and adapters live inside it, never alongside in a `tools/` sibling (a lesson learned from the earlier llm-wiki workspace which violated this)
- CSS and JavaScript must be embedded as Python string constants in `build.py`, not separate template files, to enable single-file rendering without template loaders or file-watching complexity
- Redaction of secrets (API keys, tokens, usernames, emails) is enabled by default at the converter layer, before data reaches `raw/`
- Every adapter must declare `SUPPORTED_SCHEMA_VERSIONS` and gracefully handle unknown versions by logging DEBUG and skipping unknown record types (never crashing)
- Adapter contributions are gated on exactly seven required artifacts to ensure all new adapters are testable, discoverable, and documented before PR merge

## Key Quotes

> "There is exactly ONE `llmwiki/` directory that is a Python package. Tools live inside it, not alongside it in a `tools/` sibling. (This is a lesson from the earlier llm-wiki workspace which had both.)"  
— Establishes the single-package invariant to prevent namespace collision and import confusion

> "Redaction is on by default. Username, API keys, tokens, and emails are redacted at the converter layer, before anything hits `raw/`."  
— Core privacy principle ensuring sensitive data never persists to disk

> "Adapter-flow is met when the checklist above is automatable (a GitHub Actions workflow enforces it on every PR touching `llmwiki/adapters/**`)."  
— The gate between design specification (Phase 5.25) and QA (Phase 5.5): contribution requirements must be enforceable via CI, not manual review

## Connections

- [[llmwiki]] — the agent-native session analysis tool being architecturally specified

## Contradictions

None — this is specification documentation without prior wiki claims to contradict.