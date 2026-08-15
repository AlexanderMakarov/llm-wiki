---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, llmwiki-framework-building-an-agent-native-dev-tool, agent-native-tooling, pipeline-phases, schema-versioning, adapter-extensibility, privacy-by-default]
date: 2026-08-10
source_file: 
project: llmwiki-framework-building-an-agent-native-dev-tool
model: 
last_updated: 2026-08-11
---
## Summary

This framework specification extends a standard open-source project pipeline with five new phases tailored for agent-native dev tools. The extensions include mandatory agent compatibility surveying (Phase 1.75), formalized adapter contribution flow (Phase 5.25), self-demo publishing via GitHub Pages (Phase 6.5), and living-knowledge loops (Phase 7.5). The document also locks steering decisions (Python 3.12+, privacy-first by default, MIT license, no telemetry) and establishes cross-cutting rules for schema versioning, graceful degradation, and privacy redaction.

## Key Claims

- Agent-native dev tools must complete an Agent Survey phase (1.75) before branding, delivering a per-agent compatibility matrix, test fixtures under `tests/fixtures/<agent>/`, and snapshot tests for every claimed adapter; adapters without all three ship as stubs.
- llmwiki passed validation scoring 22/25 on 2026-04-08, with the strongest gap being that no existing tool bridges `.jsonl` session files to Karpathy-style wikis.
- Adapters must follow a graceful degradation rule: silently skip unknown record types at DEBUG level, never crash the build on schema drift, and always render user-visible content (prompts and assistant text) even if the wrapping record type is unfamiliar.
- The runtime dependency floor is Python 3.12+ stdlib plus `markdown` only; optional tools like `graphifyy` are auto-detected but never required.
- Redaction is enabled by default; usernames, API keys, tokens, and emails are stripped unless explicitly whitelisted in configuration.

## Key Quotes

> "Agent-native tools need to know the `.jsonl` / session store schema for every agent they claim to support"

Justifies Phase 1.75 and the mandatory per-agent compatibility matrix and test fixtures.

> "The wiki built during development IS a growth engine — publish it and it sells the tool for you"

Core rationale for Phase 7.5 (Living Knowledge): the tool's own session history becomes a public marketing asset when published as browsable wiki.

> "Never drop user-visible content — user prompts and assistant text are always rendered even if the wrapping record is unknown"

Graceful degradation principle ensuring the pipeline remains robust to schema drift and agent version mismatches.

## Connections

- [[llmwiki]] — this framework specification is the definitive architecture and contribution guide for the project

## Contradictions

None identified. This is the source specification and does not contradict existing wiki content.