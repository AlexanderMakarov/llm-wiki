---
title: "CLI reference (part 3/8: adapters — list every adapter + its status)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, lint, knowledge-graph, adapters]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

Reference documentation for three core llmwiki CLI commands: `adapters` (list registered session adapters), `graph` (build knowledge graphs), and `lint` (enforce 17 deterministic structural quality rules). Key clarification: three lint rules (`contradiction_detection`, `claim_verification`, `summary_accuracy`) now always run as structural checks flagging empty or filler content, rather than being hidden behind `--include-llm`.

## Key Claims

- The `adapters` command lists 11 registered adapters with their default/configured status; default adapters run when no `--adapter` flag is passed.
- The `graph` command supports output formats (json, html, both) and two engines: builtin (stdlib wikilink graph) and Graphify (AI-powered with community detection and god-node analysis); Graphify requires `pip install graphifyy`.
- All 17 [[Lint]] rules are deterministic structural checks with no LLM inference, covering frontmatter completeness, link integrity, orphan detection, contradiction declarations, and provenance tracking.
- Three lint rules (`contradiction_detection`, `claim_verification`, `summary_accuracy`) now run as structural checks flagging empty/missing content, no longer gated behind `--include-llm`.
- Filler text in Contradictions sections ("None identified.", "None detected.") is ignored by lint unless paired with unnegated affirmative conflict cues; negated cues stay classified as filler.
- The `provenance_integrity` rule emits errors for broken downward hops on pages declaring `sources:` and/or `source_file:`.
- The `stale_reference_detection` rule skips pages under `wiki/sources/` and pages with `type: source` to preserve dated session records.

## Key Quotes

> "17 structural rules (all deterministic — no LLM)" — clarifies that [[Lint]] is purely structural validation despite llmwiki's broader AI capabilities.

> "Filler bodies like `None identified.`, `None detected.`, and multi-sentence `None identified. …` elaborations are not findings (unless the section also contains an *unnegated* affirmative conflict cue)" — precisely defines which negative entries lint ignores.

> "tree-sitter AST extraction for code, semantic analysis for docs, Leiden community detection, god-node analysis" — describes the Graphify engine pipeline for [[Knowledge Graph]] construction.

## Connections

- [[LLMWiki]] — the project/product these CLI commands belong to
- [[Lint]] — quality assurance system with 17 structural rules
- [[Knowledge Graph]] — the feature built by the `graph` command
- [[Adapters]] — session source adapter registry