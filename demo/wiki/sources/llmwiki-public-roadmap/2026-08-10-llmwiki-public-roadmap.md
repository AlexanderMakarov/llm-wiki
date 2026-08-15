---
title: "llmwiki Public Roadmap"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-public-roadmap, versioning, moscow-method, adapters, declined-features]
date: 2026-08-10
source_file: 
project: llmwiki-public-roadmap
model: 
last_updated: 2026-08-11
---
## Summary

The document presents a public roadmap for [[llmwiki]] tracking shipped versions (v0.1–v0.9 from April 2026) alongside in-progress work and planned features through v1.0 and beyond. Major shipped features include multiple adapters (Claude Code, Cursor, Gemini CLI, PDF, Copilot), MCP server, knowledge graph, evaluation framework, and PyPI packaging. v1.0 is planned as a stability pass with API freeze and documentation polish rather than new features, followed by post-v1.0 enhancements like knowledge graph explorer, Ollama integration, and plugin marketplace. The project uses MoSCoW prioritization to manage scope and explicitly documents declined features with design-philosophy rationale.

## Key Claims

- llmwiki shipped 9 minor versions (v0.1–v0.9) between April 8–9, 2026, each with substantial feature additions
- v1.0 is planned as a stability and API-freeze release with no new features, focusing on hardening, docs polish, and expanding platform coverage (Homebrew, PyPI)
- Several features are explicitly declined (Slack/Discord export, TUI browser, real-time collaborative editing, telemetry, Postgres backend, compiled Go/Rust binaries) with design-philosophy rationale documented in DECLINED.md
- The project follows design principles—stdlib-first rule, privacy rule, Python-first policy—that guide which features are declined
- The project uses MoSCoW (Must/Should/Could/Won't) prioritization; full breakdown with layer-by-layer assignments documented in an internal roadmap.md

## Key Quotes

> "The v1.0 release is a stability pass. No new features—just hardening." — clarifies that v1.0 is a consolidation release focused on API freeze and documentation

> "Declined items are documented with rationale in DECLINED.md. We keep the list visible so contributors don't duplicate investigation effort." — articulates the philosophy of transparent scope decisions to avoid wasted contributor effort

> Design principles cited: "stdlib-first rule," "privacy rule," "Python-first policy" — core values that guide which features are declined

## Connections

- [[llmwiki]] — subject of this public roadmap; tracks shipped versions, in-progress work, and planned features through v1.0 and beyond