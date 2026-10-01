---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
tags: [session, session-transcript, llm-wiki, claude, topic-graph, sparse-vault, fallback-mechanism, graph-rendering, sparsity-fallback, build-logic, graph-fallback, sparsity-handling, page-graph, build-optimization]
date: 2026-08-17
source_file: raw/sessions/llm-wiki/2026-07-25T12-01-llm-wiki-topic-graph-sparsity.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Implemented a sparsity threshold for the topic graph viewer to prevent empty-looking renders on small vaults. When fewer than 5 topics exist, the build falls back to the page graph (which always contains nodes since every page is one). Added focused tests, documented the behavior, and verified the fallback applies only to interactive builds, not headless paths.

## Key Claims

- Topics are dropped from the knowledge graph below two mentioning sessions, producing sparse data (1–3 nodes) in young vaults
- Below five topics, the build automatically falls back to the page graph instead of rendering the topic graph
- The fallback prevents topic pages from being generated, which is a real limitation explicitly stated in build output rather than hidden
- The page graph always produces renderable content because every page is a node
- The build prints which graph it selected and why, making the fallback decision transparent
- The headless path is unaffected; the fallback applies only to interactive sessions

## Key Quotes

> "Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small."

> "Below five topics the build falls back to the full page graph, which always has content because every page is a node."

> "The build prints which graph it chose and why, so the fallback is visible rather than mysterious."

> "Topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output."

## Connections

- [[Knowledge Graph]] (concept) — the topic graph is a structured representation within the knowledge graph; the fallback strategy ensures graceful degradation under sparse data
  - fact: Sparsity threshold is 5 topics; below this, page graph is used instead
- [[Static Site]] (concept) — the fallback strategy affects build behavior for small vaults generating static sites
  - fact: Interactive-session builds use the fallback; headless paths remain unaffected
- [[llmwiki]] (entity) — this feature is part of core build logic for handling thin topic vocabularies
  - fact: Build output explicitly reports which graph was chosen, making the fallback observable to users
- [[Wiki Synthesis]] (concept) — topic graph generation is part of synthesis; the fallback preserves content availability
  - fact: Topic pages are only generated from the topic graph; they are suppressed when graph is sparse

## Contradictions

None noted.