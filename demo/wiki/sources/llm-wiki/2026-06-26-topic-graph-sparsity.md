---
title: "Fall back to the page graph when the topic vocabulary is thin"
type: source
tags: [session, session-transcript, llm-wiki, claude, sparse-graph, graph-fallback, topic-extraction]
date: 2026-06-26
source_file: raw/sessions/llm-wiki/2026-06-26T12-01-llm-wiki-topic-graph-sparsity.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session addressed an issue where topic graphs appeared visually empty in sparse vaults. A fallback mechanism was implemented: when a vault contains fewer than 5 topics, the build switches to the page graph (which always has content because every page becomes a node). The build explicitly indicates which graph was selected and why. Topic pages are only generated when the topic graph is active; during fallback they're not generated, a limitation explicitly acknowledged rather than hidden.

## Key Claims

- Topic graphs become sparse when vaults have fewer than ~5 topics due to topics being filtered below a 2-mention threshold
- Young vaults typically produce only 2–3 topic nodes, causing the viewer to appear broken or empty
- The page graph serves as a reliable fallback because every page in the vault becomes a node, guaranteeing content
- Topic pages are only generated when using the topic graph; the fallback mode skips their generation entirely
- Build output explicitly states which graph type was selected and the reason, making the fallback visible rather than mysterious

## Key Quotes

> "That is the topic graph with almost nothing in it. Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small." — Explains why sparse vaults produce visually empty topic graphs

> "The build prints which graph it chose and why, so the fallback is visible rather than mysterious." — Design principle: transparency in fallback behavior

> "Topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output. It is a real limitation of a small vault rather than something to paper over." — Acknowledges the consequence of fallback as a real limitation rather than hidden implementation detail

## Connections

- [[Topic Graph]] — the component that becomes sparse in young vaults
- [[Page Graph]] — the fallback mechanism providing guaranteed content
- [[Build System]] — the infrastructure implementing threshold-based graph selection