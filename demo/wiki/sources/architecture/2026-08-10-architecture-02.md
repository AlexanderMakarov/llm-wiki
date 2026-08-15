---
title: "Architecture (part 2/3: Layer 2: The eight-layer build)"
type: source
tags: [wiki-add, raw-doc, session-transcript, architecture, modular-design, separation-of-concerns, build-pipeline, agent-adapters]
date: 2026-08-10
source_file: 
project: architecture
model: 
last_updated: 2026-08-11
---
## Summary

llm-wiki's internal code is organized into eight functional layers (Raw ingestion, Wiki management, Site generation, Browser UI, Distribution, Schema/docs, Adapters, and CI/ops), where each layer owns exactly one responsibility and maps 1:1 to features in the roadmap. Key architectural decisions enforce strict separation: agents drive wiki writes through slash commands (never direct writes), raw ingestion is idempotent via mtime tracking and privacy-first by default, adapters remain agent-agnostic, and build dependencies are minimized to python-markdown + stdlib.

## Key Claims

- The codebase is divided into 8 functional layers (L0–L7), each with a single, clear responsibility and 1:1 feature mapping to the roadmap
- Raw ingestion (L0) achieves idempotency by tracking mtime in `llmwiki-state.json` and skips files younger than 60 minutes to avoid live-session conflicts
- Agents cannot write to `wiki/` directly; instead slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) trigger workflows defined in [[CLAUDE.md]] and [[AGENTS.md]]
- The site build (L2) depends only on python-markdown and stdlib; all syntax highlighting runs client-side via highlight.js from a pinned CDN, keeping the build pipeline zero-external-deps
- Vault state is unified in a single active `llmwiki-state.json` per process, managed at the CLI boundary and never re-read by library modules, preventing test pollution
- The adapter registry (L6) makes the system agent-agnostic—each adapter handles discovery of its agent's session store and project slug derivation without modifying core logic

## Key Quotes

> "Each layer has one clear responsibility, and each feature in [docs/roadmap.md](roadmap.md) maps to exactly one layer."
— Establishes the core organizational principle: strict 1:1 coupling between features and layers

> "llmwiki does NOT write to `wiki/` directly. The agent does, via slash commands"
— Defines the architectural boundary: the library never mutates wiki data; agents drive all writes

> "Library modules call `resolve_state_file()` — they never re-read `config.json` for the state path... so tests and library callers cannot accidentally write into a developer's configured vault."
— Critical design pattern documented to prevent test isolation leaks

## Connections

- [[CLAUDE.md]] — defines the agent schema and slash-command workflows that execute L1 (Wiki) writes
- [[AGENTS.md]] — multi-agent mirror of CLAUDE.md for Codex/OpenCode/Gemini platforms
- [[docs/roadmap.md]] — feature list organized by Phase × Layer × Item, enabling 1:1 mapping

## Contradictions

None noted — this is architectural specification.