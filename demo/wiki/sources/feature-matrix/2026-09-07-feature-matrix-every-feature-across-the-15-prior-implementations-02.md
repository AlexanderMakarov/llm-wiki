---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 2/3: F · Multi-agent support)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, comparative-analysis, roadmap, prior-art]
date: 2026-09-07
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-07
---
## Summary

This session documents Part 2 (feature categories F–O) of a three-part feature matrix comparing [[llmwiki]] against 15 prior implementations. It establishes feature priorities using a five-star rating system, catalogs which features derive from prior art versus llmwiki innovations, and maps each to development phases (v0.1 through v0.3) or intentional deferral. Key coverage spans multi-agent support schemas ([[CLAUDE.md]], [[AGENTS.md]], [[GEMINI.md]]), infrastructure components (file watchers, MCP server), search & discovery (client-side indexing, bidirectional [[Wikilinks]]), comprehensive testing and [[GitHub Actions]] automation, privacy & security features (username/API key/email redaction, Gitleaks scanning, localhost-only binding), UX polish (typography, accessibility, motion preferences), and operational features (contradiction tracking, stale-page detection, version management).

## Key Claims

- Five-star innovations with no prior art include the [[Adapters|adapter registry]] (F5), client-side search indexing (H1), bidirectional backlinks (H5), privacy redaction systems (M1–M3), and Gitleaks secret scanning (I6, M4)—indicating distinct novel contribution over 15 prior systems.

- Features are stratified across three phases: v0.1 (~40 core features including schemas, adapters, testing, CI/CD); v0.2 (advanced infrastructure like file watchers, MCP server, contextual injection hooks); v0.3 (stretch goals including [[SQLite]] backend, FTS5 search, Ollama local LLM, cross-project wiring).

- Several high-value features are intentionally deferred or marked "won't": the eval framework (I4, declined per #154; replaced by `llmwiki lint`), Supabase/Postgres backend (G6), Sentry error tracking (G7), and loading states (N7).

- Privacy and security features receive uniformly high priority (five-star) with explicit no-telemetry and no-PII-in-fixtures requirements (M5–M8), reflecting design commitment to safe handling of sensitive session data.

## Key Quotes

> "Adapter registry (`llmwiki.adapters.REGISTRY`) — ⭐⭐⭐⭐⭐ — **None** (bashiraziz has folders, not registry)" — Establishes the formal registry as a five-star innovation moving beyond folder-based plugin loading.

> "I4 | Eval framework (LLM-judged / structural wiki scoring) — ⭐⭐⭐ — xoai — declined (#154) — never shipped; use `llmwiki lint`" — Documents deliberate deferral of LLM-based evaluation in favor of simpler linting.

> "Username redaction (`/Users/you/` → `/Users/USER/`) — ⭐⭐⭐⭐⭐ — **None**" — Highlights privacy as a five-star, novel feature with no prior art implementation.

## Connections

- [[llmwiki]] (project) — the subject system being feature-planned and compared against 15 prior implementations.
  - fact: Features span 10 major categories (F–O) with ~60 distinct features cataloged.
  - fact: Phased delivery: v0.1 is launch with ~40 core features; v0.2 adds advanced infrastructure; v0.3 includes optional backends and integrations.

- [[Adapters]] (system) — modular plugin architecture with formal registry (F5) and version tracking (F6).
  - fact: Adapter registry is a five-star innovation with no prior art, enabling graceful degradation on unknown record types (F7).
  - fact: Core feature supporting multi-agent schemas: [[CLAUDE.md]] (all 15 prior implementations), [[AGENTS.md]] (SamurAIGPT, Ss1024sS, bashiraziz), [[GEMINI.md]] (SamurAIGPT).

  - fact: Establishes baseline for agent memory and contextual injection.

- [[Codex CLI]] (tool) — referenced as prior art for file watching (G2, via bitsofchris, kytmanov) and MCP server design (G4, via bitsofchris, lucasastorian).
  - fact: llmwiki v0.2 ships MCP server to expose wiki as callable tools to agents.

- [[SQLite]] (backend) — structured query backend deferred to v0.3 (G5); prior art from bashiraziz.
  - fact: Pairs with FTS5 full-text search (H2) and server-side result reranking (H3).

- [[Static Site]] (deployment) — [[GitHub Pages]] demo relies on client-side search index (H1, five-star innovation) and JSON index.
  - fact: Enables offline search and discovery without requiring server infrastructure.

- [[Knowledge Graph]] (concept) — supports backlinks feature (H5, five-star innovation, no prior art); bidirectional wikilink discovery.
  - fact: Foundational for wiki navigation and [[Wiki Synthesis|synthesis]].

- [[GitHub Actions]] (platform) — comprehensive CI/CD pipeline with lint/test (J1), pages deployment (J2), release automation (J3), and Dependabot tracking (J7).
  - fact: All five core CI/CD features ship in v0.1–v0.2, establishing v0.1 as "production-ready."

## Contradictions

None. The feature matrix represents a deliberate roadmap rather than a statement of current implementation. Features marked "won't" (G6, G7, N7) and deferred to later phases are explicit design decisions, not contradictions with other documented claims.