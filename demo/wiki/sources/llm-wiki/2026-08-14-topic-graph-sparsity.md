---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
tags: [session, session-transcript, llm-wiki, claude, topic-graph, sparse-vault, fallback-mechanism, graph-rendering, sparsity-fallback, build-logic]
date: 2026-08-14
source_file: raw/sessions/llm-wiki/2026-07-25T12-01-llm-wiki-topic-graph-sparsity.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session implemented a fallback mechanism for sparse topic vocabularies in [[llmwiki]]. When a vault indexes fewer than five topics (below the generation threshold), the build now falls back to rendering the full page graph instead of displaying an empty topic graph viewer. The change is confined to interactive sessions; headless synthesis is unaffected. A test was added to lock the behavior, and a CHANGELOG entry was written.

## Key Claims

- Topics are dropped from the graph when they appear in fewer than two mentioning sessions, resulting in sparse vocabularies in young vaults.
- The fallback threshold is set at fewer than five topics; below this, the page graph is rendered instead.
- When the fallback is triggered, no topic pages are generated at all—it is a real limitation rather than a cosmetic fix.
- The build output explicitly indicates which graph was chosen and the reason for the fallback.
- The headless synthesis path is unaffected; fallback logic applies only to interactive-session builds.

## Key Quotes

> "Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small."

> "below five topics the build falls back to the full page graph, which always has content because every page is a node"

> "Yes — topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output. It is a real limitation of a small vault rather than something to paper over."

## Connections

- [[llmwiki]] (entity) — the wiki system being modified with fallback logic.
  - fact: Topic graph rendering now detects sparsity and switches strategies.
- [[Static Site]] (entity) — the build process where topic and page graph rendering occurs.
  - fact: Fallback logic resides in the build's graph selection step, not headless fixtures.
- [[Knowledge Graph]] (entity) — the topic graph is a component of the knowledge graph structure.
  - fact: Sparsity handling preserves graph integrity by falling back to a denser alternative.

## Contradictions

- None noted.