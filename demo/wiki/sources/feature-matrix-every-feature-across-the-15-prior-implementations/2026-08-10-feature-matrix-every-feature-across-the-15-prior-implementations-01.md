---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix-every-feature-across-the-15-prior-implementations, product-roadmap, prior-art-survey, system-architecture]
date: 2026-08-10
source_file: 
project: feature-matrix-every-feature-across-the-15-prior-implementations
model: 
last_updated: 2026-08-11
---
## Summary

This session documents a comprehensive feature matrix comparing [[llm-wiki]] against 15 prior implementations of LLM-based wiki systems. The researcher cloned and inspected every referenced repository, cataloging ~70 features across six domains (core workflows, input adapters, page types, output/viewer, distribution, and multi-agent support), rating each for target value (⭐ to ⭐⭐⭐⭐⭐), and marking which are novel to llm-wiki versus inherited from prior art. The matrix serves as a prioritized roadmap, with most god-level and strong must-have features (~40 total) targeted for v0.1–v0.2.

## Key Claims

- The [[Claude Code]] `.jsonl` adapter (B1) has no prior art and is identified as a v0.1 kill-feature.
- Several output/viewer features (D2–D6, D9–D10, D13–D16) with 4–5 star ratings are net-new inventions for llm-wiki.
- The adapter registry (F5) is a novel architectural pattern; prior work (bashiraziz) used folder-based organization instead of a registry.
- ~40 features are rated 4–5 stars and primarily targeted for v0.1–v0.2; ~30 are rated 2–3 stars for v0.3+ or won't-have.
- 15 distinct prior implementations were surveyed, spanning diverse approaches (SamurAIGPT, kfchou, bashiraziz, Ss1024sS, hsuanguo, louiswang524, and others).

## Key Quotes

> "Method: Cloned and inspected every referenced repo. Listed every feature I found in any of them, rated each by target value to llmwiki (1–5), and marked which ones are already present in at least one reference implementation vs. which are a net-new invention for llmwiki."

This statement grounds the matrix's credibility through systematic enumeration of prior art.

> ⭐⭐⭐⭐⭐: God-level — killer feature, llmwiki ships without it is pointless

The value legend frames prioritization around existential ship-blockers for v0.1.

> **None** (in the "Prior art" column for B1, D2–D6, D13–D16)

These entries signal opportunities for llm-wiki to differentiate from prior work.

## Connections

- [[Claude Code]] — killer input adapter (B1, v0.1)
- [[Codex CLI]] — planned input adapter (B2, v0.1 stub → v0.2 full)
- [[Obsidian]] — vault format for bidirectional adapter (B3, D18, v0.1–v0.2)