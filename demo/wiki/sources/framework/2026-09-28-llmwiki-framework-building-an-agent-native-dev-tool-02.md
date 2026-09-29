---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 2/3: Phase 3 — Structure)"
type: source
tags: [wiki-add, raw-doc, session-transcript, framework, adapter-contribution-flow, architecture, privacy-by-default, performance-budgets]
date: 2026-09-28
source_file: 
project: framework
model: 
last_updated: 2026-09-28
---
## Summary

This framework document specifies Phases 3–6 of [[llmwiki]], establishing hard architectural rules: one Python package (not dual), CSS/JS embedded as string constants, and enforced performance budgets (cold build < 15s, site < 50 MB). It introduces a formalized contribution contract for [[Adapters]] (Phase 5.25) requiring fixture, snapshot test, and documentation; codifies privacy-first rules (secret redaction on by default) and schema-versioning strategy (graceful adapter degradation); and outlines pre-launch QA and release procedures.

## Key Claims

- llmwiki uses exactly one `llmwiki/` Python package; tools live inside it, never in a sibling `tools/` directory (lesson from an earlier workspace that had dual packages)
- CSS and JavaScript are embedded as Python string constants in `build.py` for single-file rendering, avoiding template loaders and file-watching complexity
- Performance budgets are enforced gates: cold build < 15s (measured 9s), incremental < 1s (0.4s), total site < 50 MB (measured 24 MB); exceeding metrics block changes unless preceded by an optimization PR
- Secret redaction (API keys, tokens, emails) is enabled by default at the converter layer, before data enters the vault
- Each adapter declares `SUPPORTED_SCHEMA_VERSIONS` and gracefully degrades (logs DEBUG, continues) on unknown record types instead of crashing
- Adapter contributions require a formal contract: PR must include adapter file, fixture (< 50 KB, no real PII), snapshot test, documentation page, changelog entry, and README line; GitHub Actions auto-enforces the review checklist
- No telemetry, no auth/accounts/sync, no cloud features; binding defaults to `127.0.0.1` (explicit `--host 0.0.0.0` required for LAN/public access)

## Key Quotes

> "There is exactly ONE `llmwiki/` directory that is a Python package. Tools live inside it, not alongside it in a `tools/` sibling. (This is a lesson from the earlier llm-wiki workspace which had both.)"

Clarifies a critical structural decision to prevent import confusion.

> "CSS/JS are Python string constants inside `build.py` — single-file rendering, no template loader, no file watching complexity."

A pragmatic trade-off: simplified deployment and portability over template flexibility.

> "If any metric exceeds its budget, the offending change is blocked or must be preceded by a measurement + optimisation PR."

Performance is a gated property, enforced via continuous measurement, not aspirational.

> "Secret redaction is on by default. API keys, tokens, and emails are redacted at the converter layer, before anything hits `raw/`."

Privacy-first default: secrets never touch the vault unless explicitly opted out.

> "Adapter-flow is met when the checklist above is automatable (a GitHub Actions workflow enforces it on every PR touching `llmwiki/adapters/**`)."

Formalizes community contribution by encoding the full contract into automation.

## Connections

- [[llmwiki]] (entity) — the Python tool and framework being architected
  - fact: Single Python package directory (not dual or alongside `tools/`)
  - fact: CSS/JS embedded as Python constants in build.py
  - fact: Performance budgets enforced as blocking gates (cold build < 15s, site < 50 MB)
  - fact: Secret redaction on by default at converter layer
  - fact: No telemetry, auth, or cloud features; local-only by design
- [[Adapters]] (entity) — extensible modules for ingesting sessions from different agents
  - fact: Phase 5.25 formalizes contribution with required fixture, snapshot test, documentation, changelog, and README line
  - fact: Each adapter declares SUPPORTED_SCHEMA_VERSIONS for backward-compatible graceful degradation
  - fact: GitHub Actions workflow auto-enforces review checklist on PRs touching llmwiki/adapters/**
  - fact: Adapter code must handle unknown record types gracefully (log, skip) rather than crash
- [[Wiki Synthesis]] (concept) — the process of building wiki pages from sessions
  - fact: Syntax highlighting uses highlight.js CDN at view time, no build-time parsing
  - fact: Incremental build performance target is < 1s (measured 0.4s)

## Contradictions

None identified. This is a forward-looking framework specification.