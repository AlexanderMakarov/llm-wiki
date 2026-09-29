---
title: "Architecture (part 3/3: Design principles)"
type: source
tags: [wiki-add, raw-doc, session-transcript, architecture, design-principles, offline-capability, privacy-first, modularity, agent-agnostic]
date: 2026-09-28
source_file: 
project: architecture
model: 
last_updated: 2026-09-28
---
## Summary

This document codifies six core design principles guiding [[llmwiki]] (entity) architecture: minimal runtime dependencies (markdown only), privacy-by-default redaction, idempotent operations, localhost-only execution (no network/telemetry), single-file-per-concern organization, and agent-agnostic core logic. These constraints enable deterministic, offline-capable builds while preserving user control over publication and data sensitivity.

## Key Claims

- The runtime has exactly one dependency: the `markdown` library; syntax highlighting is client-side via CDN-loaded highlight.js.
- Deterministic and offline-capable builds are achieved through this minimal-dependency and client-side approach.
- All sensitive data must be redacted before reaching disk, enforcing privacy by default.
- Every command is designed to be idempotent—re-running is safe and cheap.
- The system operates localhost-only with zero network calls and telemetry.
- The HTML rendering (CSS, JavaScript, templates) lives entirely in a single `build.py` file.
- The `convert.py` core is agent-agnostic; [[Adapters]] (entity) translate between different agent outputs.

## Key Quotes

> "Stdlib first. Runtime dep: `markdown` only."—establishes the minimalism constraint that keeps builds deterministic and offline-capable.

> "Privacy by default. Redact everything sensitive before it hits disk."—core safety principle for user data.

> "Localhost only. No network, no telemetry, no cloud. The user controls if/when to publish."—clarifies the trust model and user sovereignty.

> "One file per concern. build.py is one file, not a folder of templates."—design discipline for maintainability.

> "Agent-agnostic core. `convert.py` doesn't know which agent produced the .jsonl."—separates business logic from adapter diversity.

## Connections

- [[llmwiki]] (entity) — these design principles guide all architectural decisions.
  - fact: The system is built around minimal dependencies and offline-first operation.
- [[Adapters]] (entity) — the agent-agnostic core delegates format translation to them.
  - fact: `convert.py` has no knowledge of which agent produced input; adapters handle agent-specific translation.
- [[Static Site]] (entity) — deterministic builds enable reliable static output.
  - fact: Stdlib-only dependencies and client-side syntax highlighting ensure reproducible builds.
- [[Wiki Synthesis]] (concept) — these principles structure the synthesis workflow.
  - fact: Idempotency and privacy-by-default are operational guarantees during synthesis.