---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
tags: [session, session-transcript, llm-wiki, claude, knowledge-graph, graph-fallback, sparse-data, topic-graph]
date: 2026-07-24
source_file: raw/sessions/llm-wiki/2026-07-24T12-01-llm-wiki-topic-graph-sparsity.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session addressed a rendering issue where the topic graph appeared empty-looking in viewers when vault data was sparse (1–2 nodes). A threshold-based fallback was implemented: below 5 topics, the build switches from the topic graph to the page graph (which always has content). This design is transparent — the build logs which graph was chosen and why — and treats the sparsity as a real limitation of young vaults rather than a problem to hide.

## Key Claims

- Topic graphs with 1–2 nodes render as visually empty, appearing broken to users
- Young vaults often produce 1–3 topics due to llmwiki's 2-session minimum filter for topic inclusion
- Below 5 topics, the build falls back to the page graph, which always contains all pages as nodes
- Topic pages are generated only from the topic graph and will not be written when the fallback is active
- The build explicitly reports which graph was chosen and the reason for the selection

## Key Quotes

> "That is the topic graph with almost nothing in it. Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small." — Explains why sparse topic data causes poor rendering and motivates the threshold

> "The build prints which graph it chose and why, so the fallback is visible rather than mysterious." — Shows the design principle of transparency over silent degradation

> "It is a real limitation of a small vault rather than something to paper over." — Clarifies that the fallback honestly represents constraints of early-stage vaults

## Connections

- [[Knowledge Graph]] (concept) — the graph structures whose density triggers fallback behavior
  - fact: Topic graphs with fewer than 5 nodes are considered too sparse for acceptable rendering
  - fact: Page graphs are used as a fallback because every page is a node, guaranteeing visual content
- [[Static Site]] (system) — the build process that selects and generates the appropriate graph
  - fact: The build output explicitly logs which graph was chosen and the threshold that triggered selection
- [[llmwiki]] (project) — the system where sparse topic vocabulary is common in young vaults
  - fact: The 2-session mention minimum for topic filtering makes new vaults likely to fall below the 5-topic threshold