---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 3/3: Phase 6.5 — Self-Demo (NEW))"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-framework-building-an-agent-native-dev-tool, dogfooding, schema-versioning, ci-github-pages, privacy-first, agent-dev-tools]
date: 2026-08-10
source_file: 
project: llmwiki-framework-building-an-agent-native-dev-tool
model: 
last_updated: 2026-08-11
---
## Summary

This document completes the [[llmwiki]] framework (phases 6.5–8) and defines patterns specific to agent-native dev tools—a category the parent framework didn't explicitly cover. Key patterns include: self-demo published via CI to GitHub Pages using synthetic data (privacy-preserving); a "living knowledge" public wiki that doubles as meta-documentation and marketing; a schema-versioning playbook for graceful handling of upstream agent format changes; and a dogfooding loop where the tool validates itself on its own output. These patterns are intended to be inherited and extended by future tools in this category (Cursor wiki, Cline browser, multi-agent viewer).

## Key Claims

- Self-demo should use synthetic/curated fixtures, not author's real sessions, to preserve privacy while proving the tool works on representative UI states
- GitHub Actions on tag push should build the site to `site/` and publish to GitHub Pages; every release auto-updates the demo with zero manual effort
- Public wiki and release notes must cross-link; community feedback on wiki pages (via GitHub Issues) feeds back into the framework
- When an upstream agent changes its output schema, graceful degradation is preferred; only breaking changes should trigger new adapter versions (`claude_code_v3.py` alongside `claude_code_v2.py`)
- Dogfooding closes a feedback loop: dev sessions → llmwiki build → output → backlog (tasks.md) → next dev cycle, enabling continuous self-validation
- Agent-native dev tools should inherit and extend this framework as a pattern, not violate the parent framework

## Key Quotes

> "Every dev tool that produces browsable output should publish its own dev history as the demo."
— Establishes the core principle: the tool's own output is its landing page, eliminating the need for screenshots or "look here's what it looks like" claims.

> "For privacy reasons, llmwiki's self-demo uses a synthetic corpus under demo/, not the author's real session history."
— Privacy-by-design: synthetic fixtures are hand-curated, cover all UI states (short sessions, long sessions, sub-agents, code blocks, tool calls, errors), and are committed to the repo.

> "The wiki built during development IS a growth engine. Every release refreshes the public wiki with new insights, decisions, and patterns extracted from dev sessions."
— Links Phase 7.5 to marketing strategy: the public wiki serves both as documentation and SEO; visitor engagement and feedback drive the backlog.

> "llmwiki tracks its own development with llmwiki. Every dev session on llmwiki is already being captured by [[Claude Code]]. ./sync.sh pulls those sessions into raw/sessions/llmwiki/."
— Closes the dogfooding loop: self-referential design allows continuous validation on real (synthetic) workloads.

> "When an agent ships a new .jsonl schema: If graceful degradation works: add the version to SUPPORTED_SCHEMA_VERSIONS… If the change is breaking: ship a new adapter file (claude_code_v3.py) alongside the old one, route by version."
— Schema-versioning strategy: backward compatibility preferred; new adapters only for breaking changes, minimizing user friction.

## Connections

- [[llmwiki]] — this document defines phases 6.5–8 of its development framework and meta-patterns
- [[Claude Code]] — upstream agent whose session `.jsonl` schema llmwiki must track and gracefully degrade when formats change

## Contradictions

None noted; this document explicitly states these extensions do not violate the parent framework but extend it with patterns specific to agent-native dev tools.