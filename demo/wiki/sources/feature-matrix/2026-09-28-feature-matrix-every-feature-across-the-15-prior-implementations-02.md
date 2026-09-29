---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 2/3: F · Multi-agent support)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, design-doc, scope-roadmap, competitive-analysis]
date: 2026-09-28
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-28
---
## Summary

This is part 2 of a three-part **Feature Matrix** document benchmarking llmwiki's implementation across 50+ features against 15 prior knowledge-system projects (SamurAIGPT, bashiraziz, bitsofchris, remember-md, kytmanov, hsuanguo, lucasastorian, xoai, sinzin91, and others). It catalogs features across eight domains—multi-agent support, infrastructure, search/discovery, testing, CI/CD, documentation, configuration, privacy/security, UX polish, and operations—rating each by importance (1–5 stars), documenting prior art, and mapping to a phased rollout (v0.1, v0.2, v0.3, or "won't do"). Strategic decisions emerge: the adapter registry and multi-agent schemas are 5-star v0.1 innovations; privacy (redaction, no telemetry, Gitleaks, localhost binding) is a core differentiator with no prior art; some capabilities are deliberately deferred (SQLite FTS, Postgres backend) or declined (LLM-judged eval framework per #154).

## Key Claims

1. The **adapter registry (F5)** is a 5-star v0.1 innovation with "None" in the Prior art column—no prior system implemented a versioned, extensible registry; schema version tracking (F6) and graceful degradation (F7) depend on it.

2. **Privacy and security (M1–M6) comprise six 5-star v0.1 features with zero prior art**: username redaction, API key/token masking, email redaction, Gitleaks CI scanning, localhost-only binding, and zero telemetry—these are llmwiki differentiators against all 15 prior systems.

3. **Live-session detection (G10, 5-star v0.1)** and **MCP server (G4, 5-star v0.2)** are infrastructure innovations that expose the wiki to external agents; G10 has no prior implementation.

4. **Testing and quality (I1–I8)** are v0.1 core: pytest, snapshot tests, E2E fixtures, link checking, Gitleaks, and privacy checks are 5-star priorities, with snapshot tests and privacy checks being novel (no prior art).

5. **Eval framework (I4) was explicitly declined (#154)** in favor of rule-based `llmwiki lint`; this is a deliberate trade-off against LLM-judged systems like xoai.

6. **Supabase/Postgres backend (G6) and Sentry telemetry (G7) are marked "won't"**—reflecting hard choices toward local-first architecture and zero third-party telemetry, despite lucasastorian choosing cloud backends.

## Key Quotes

> **Adapter registry innovation**: F5 ("Adapter registry `llmwiki.adapters.REGISTRY`") is rated ⭐⭐⭐⭐⭐ v0.1 with Prior art "**None** (bashiraziz has folders, not registry)"—a novel architectural choice.

> **Privacy-first is core**: M1–M6 (username redaction, API key/token masking, email redaction, Gitleaks, localhost binding, zero telemetry) are all ⭐⭐⭐⭐⭐ v0.1 with "**None**" in Prior art—llmwiki is pioneering privacy-as-default.

> **MCP Server and live-session hooks**: G4 (MCP server, ⭐⭐⭐⭐⭐ v0.2) and G10 (live-session detection, ⭐⭐⭐⭐⭐ v0.1) expose wiki to external agents; G10 has "**None**" as prior art.

> **Eval framework declined**: I4 (Eval framework, ⭐⭐⭐, "declined (#154)") was rejected in favor of `llmwiki lint`—a deliberate simplification against prior systems like xoai.

## Connections

- [[llmwiki]] (entity) — the subject system; this feature matrix is a strategic benchmarking and scope document comparing llmwiki against 15 prior implementations
  - fact: Multi-agent support (F1–F7) is core v0.1, with the adapter registry (F5) being a novel, unimplemented feature
  - fact: Six privacy features (M1–M6) are 5-star v0.1 with zero prior art, positioning llmwiki as privacy-first

- [[Adapters]] (entity) — F5 (adapter registry) is the central innovation enabling multi-format, versioned ingestion; F6–F7 (versioning and graceful degradation) depend on it
  - fact: Registry-based architecture with schema versioning (F6) differs from folder-based approaches in bashiraziz

- [[MCP Server]] (entity) — G4, exposing wiki as tools to agents; 5-star v0.2 with prior art in bitsofchris and lucasastorian
  - fact: Core infrastructure for multi-agent integration

- [[GitHub Actions]] (entity) — J-series CI/CD (J1–J7): lint+test on PR, GitHub Pages deploy, release automation; J1–J2 are 5-star v0.1
  - fact: Gitleaks secret scanning (M4 integration into CI) is 5-star v0.1

- [[Static Site]] (entity) — the output artifact fed by H-series (search/discovery), N-series (UX polish), K-series (documentation)
  - fact: Client-side search index (H1, 5-star v0.1) is the discovery mechanism; server-side FTS (H2) deferred to v0.3

- [[Wiki Synthesis]] (concept) — the ingestion and build process that infrastructure (G) and testing (I) features support; phased rollout governs maturity
  - fact: Infrastructure (G1–G10) enables sync and exposure; testing (I1–I8) validates quality; documentation (K1–K15) guides users

- [[Lint Rules]] (concept) — I5 (link checker), O2 (stale-page detection) are 4–5 star v0.1 features; I4 (LLM-judged eval) explicitly declined (#154)
  - fact: Rule-based linting chosen over LLM-judged eval for simplicity and cost

- [[Knowledge Graph]] (concept) — H5 (bidirectional backlinks via `[[wikilinks]]`) is 5-star v0.1 with no prior explicit art
  - fact: Backlinks enable cross-page discovery alongside client-side search (H1)