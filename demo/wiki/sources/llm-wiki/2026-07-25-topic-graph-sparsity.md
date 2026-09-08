---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
tags: [session, session-transcript, llm-wiki, claude, topic-graph, sparse-vault, fallback-mechanism, graph-rendering]
date: 2026-07-25
source_file: raw/sessions/llm-wiki/2026-07-25T12-01-llm-wiki-topic-graph-sparsity.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

When young vaults produce only 2–3 topics (because topics are filtered to only those mentioned in 2+ sessions), the topic graph viewer renders empty and broken. The session implemented a five-topic threshold: below this, the build falls back to the page graph, which always contains content since every page is a node. Topic pages are not generated in sparse-vault mode, and the build explicitly reports which graph was chosen.

## Key Claims

- Topics are filtered to only those mentioned in 2+ sessions, resulting in sparse graphs for young vaults
- A two-to-three-node topic graph renders as empty or broken in the viewer
- The build implements a five-topic threshold to decide between topic graph and page graph fallback
- Topic pages are only generated when the vault has 5+ topics; below this threshold none are written
- The build explicitly reports which graph type was selected and why, making the fallback visible rather than mysterious

## Key Quotes

> "Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small."

> "Below five topics the build falls back to the full page graph, which always has content because every page is a node."

> "It is a real limitation of a small vault rather than something to paper over."

## Connections

- [[Knowledge Graph]] (concept) — sparse topic graphs trigger the fallback strategy
  - fact: Topics are filtered to only those mentioned in 2+ sessions
- [[Wiki Synthesis]] (concept) — the build process implementing fallback logic and determining whether topic pages are generated
  - fact: Topic pages are only generated when the vault has 5+ topics
- [[Static Site]] (concept) — the output format and graph type affected by vault size
