---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 3/3: Phase 6.5 — Self-Demo (NEW))"
type: source
tags: [wiki-add, raw-doc, session-transcript, framework, self-demo, dogfooding, schema-versioning, living-knowledge, synthetic-corpus]
date: 2026-09-28
source_file: 
project: framework
model: 
last_updated: 2026-09-28
---
## Summary

This framework extends parent patterns with agent-native dev tool specifics for Phases 6.5–8: automated self-demo publishing on tag push via CI/CD, a public "living knowledge" wiki doubling as documentation and marketing, graceful degradation for upstream schema changes via version routing, and a dogfooding loop where the tool's own output drives development priorities. All demos use synthetic corpora for privacy, not real session data.

## Key Claims

- Agent-native dev tools' most effective demo is their own development history, published automatically via tag-push CI workflow
- Self-demo and public wiki use a curated synthetic corpus for privacy, never real session data
- Upstream schema changes should be handled via version routing in adapters, enabling graceful degradation without blocking releases
- The public wiki doubles as both meta-documentation (transparency about how the tool is built) and SEO-driven marketing
- The tool's own wiki output should feed back into GitHub Issues, closing a self-improvement loop where outputs become backlog items

## Key Quotes

> "llmwiki's killer demo is its own repo." — Captures the central principle that a dev tool producing browsable output should publish its own development history as the canonical example.

> "The wiki built during development IS a growth engine. Publish it." — Explains why the documentation wiki is both internal resource and community engagement mechanism.

> "The loop closes: the tool's own output drives the tool's own backlog." — The dogfooding cycle: tool processes its own sessions, discovers issues in the output, opens GitHub Issues, which feed development priorities.

## Connections

- [[llmwiki]] (entity) — the agent-native dev tool this framework describes
  - fact: Its own development wiki serves as both demo and marketing engine
- [[GitHub Actions]] (entity) — automates build and publish on tag push
  - fact: Enables zero-manual-effort demo and wiki updates on every release
- [[GitHub Pages]] (entity) — hosts demo and public wiki
  - fact: Visitors see exact tool output; no screenshots or staged examples
- [[Claude Code]] (entity) — source of session transcripts
  - fact: Every development session is automatically captured for dogfooding
- [[Adapters]] (entity) — convert session formats to wiki content
  - fact: Upstream schema changes use version routing for graceful degradation without requiring intervention
- [[Wiki Synthesis]] (concept) — conversion of sessions to indexed wiki pages
  - fact: Must use synthetic, privacy-preserving corpus instead of real session data
- [[Knowledge Graph]] (concept) — enables topic navigation via cross-references
  - fact: Release notes and wiki pages cross-link, closing feedback loops