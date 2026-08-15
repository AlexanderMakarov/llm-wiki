---
title: "Architecture (part 3/3: Adding an adapter)"
type: source
tags: [wiki-add, raw-doc, session-transcript, architecture, adapter-framework, design-principles, privacy-by-default, deterministic-builds, offline-capable]
date: 2026-08-10
source_file: 
project: architecture
model: 
last_updated: 2026-08-11
---
## Summary

Documented the adapter framework for [[llmwiki]], specifying a six-step standardized process to add a new LLM agent adapter and articulating six core design principles: stdlib-only runtime, privacy-by-default redaction, idempotency, localhost-only architecture, single-concern files, and agent-agnostic core logic.

## Key Claims

1. Adding an adapter requires exactly six components: a new Python file at `llmwiki/adapters/<agent>.py`, a fixture, a snapshot test, a doc page, a README line, and a CHANGELOG entry.
2. The runtime dependency is `markdown` library only; syntax highlighting runs client-side via CDN-loaded highlight.js to maintain determinism and offline capability.
3. All sensitive data must be redacted before it reaches disk—this is a non-negotiable design constraint.
4. The core `convert.py` module is deliberately agent-agnostic; adapter modules provide the sole translation layer between specific LLM outputs and the canonical format.
5. Every command re-run is safe and cheap due to idempotent design; the system has no network calls, telemetry, or cloud dependencies.

## Key Quotes

> "Runtime dep: `markdown` only. Nothing else." — captures the stdlib-first philosophy that keeps builds deterministic and offline-capable

> "Agent-agnostic core. `convert.py` doesn't know which agent produced the .jsonl. Adapters translate." — clarifies the architectural boundary that allows new adapters without modifying the core system

## Connections

- [[llmwiki]] — the project being architected
- [[Adapter Framework]] — the primary system design topic of this document
- [[Framework]] — contains the detailed adapter contract (framework.md §5.25 Adapter Flow)

## Contradictions

None identified. This is prescriptive forward-facing architecture documentation.