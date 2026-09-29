---
title: "Architecture (part 2/3: Layer 2: The eight-layer build)"
type: source
tags: [wiki-add, raw-doc, session-transcript, architecture, build-pipeline, session-normalization]
date: 2026-09-28
source_file: 
project: architecture
model: 
last_updated: 2026-09-28
---
## Summary

This architectural document describes llmwiki's eight-layer internal design, from raw session conversion (L0) through CI/ops automation (L7). Each layer isolates a single responsibility: L0 normalizes and redacts sessions from agent stores idempotently via state tracking, L1 delegates wiki mutations to agents via slash commands, L2 generates static HTML using minimal dependencies, L3 handles browser interactivity in vanilla JS, L4 manages installation and distribution, L5 documents schemas and workflows, L6 plugs in per-agent session discovery via adapters, and L7 automates testing and deployment. The design prioritizes agent-agnosticism, privacy, and keeping the build pipeline fast and dependency-light.

## Key Claims

- llmwiki is organized into eight functional layers (L0–L7), each with a single, non-overlapping responsibility and clear owner
- Layer 0 (Raw) achieves idempotency by tracking modification times in `llmwiki-state.json` and is privacy-first, redacting API keys, tokens, and usernames by default
- Layer 1 does not allow direct library writes to `wiki/`; only agents can mutate it via slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) that trigger schema-defined workflows
- Layer 2 (Site) deliberately avoids heavy dependencies—using only stdlib + python-markdown—and defers syntax highlighting to the browser via a pinned CDN copy of highlight.js
- Layer 6 (Adapters) makes the system agent-agnostic: each adapter discovers sessions per-agent type, while all parsing, filtering, and redaction logic is centralized in `convert.py`
- Vault state is managed at the CLI border; library modules never re-read `config.json` for state paths, preventing accidental writes to developer vaults during testing

## Key Quotes

> "llmwiki does NOT write to `wiki/` directly. The agent does, via slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) that execute the workflows in the schema file."

This establishes the core design principle: the library is passive, and agents drive mutations, enabling agent-specific workflows while keeping the core agnostic.

> "Idempotent — mtime tracked in `<vault>/llmwiki-state.json` (unified queue + sync + synth + quarantine state)"

Centralized vault state management is the backbone of correctness; tracking ensures re-runs, crashes, and concurrent processes don't corrupt or re-process the same session.

> "syntax highlighting runs in the browser via highlight.js loaded from a pinned jsdelivr CDN (v0.5, #73), so the build pipeline itself stays stdlib-only."

This exemplifies the philosophy: minimize build-time computation and dependencies; defer heavy lifting to the client to keep builds fast and reproducible.

## Connections

- [[llmwiki]] (entity) — the system being architected
  - fact: Organized into eight layers (L0–L7) with non-overlapping concerns and clear ownership
  - fact: Vault state centrally tracked in `llmwiki-state.json` per process to ensure idempotency

- [[Adapters]] (entity) — Layer 6, per-agent session discovery
  - fact: Each adapter subclass discovers and walks the session store for one agent type
  - fact: All parsing, filtering, redaction, and normalization is centralized in `convert.py`, avoiding per-adapter duplication

- [[Static Site]] (entity) — Layer 2, HTML generation
  - fact: Converts `raw/sessions/` and hand-authored `wiki/` files to static HTML using python-markdown
  - fact: Build pipeline is lightweight (stdlib + one dependency); syntax highlighting deferred to browser to avoid build-time overhead

- [[GitHub Actions]] (entity) — Layer 7, CI/CD automation
  - fact: `ci.yml` runs lint, tests, and build smoke-tests on every push
  - fact: `pages.yml` builds and deploys to GitHub Pages on version tag pushes

- [[Wiki Synthesis]] (concept) — L0–L1 process of converting sessions into wiki content
  - fact: L0 normalizes sessions from agent stores into markdown; L1 agents write wiki mutations via schema-driven slash commands
  - fact: Two-layer design keeps conversion logic shared while letting each agent define its own workflows