---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, framework, agent-native-tools, adapter-contract, agent-compatibility, schema-versioning]
date: 2026-09-28
source_file: 
project: framework
model: 
last_updated: 2026-09-28
---
## Summary

This framework document specifies the extended pipeline and governance rules for llmwiki, an agent-native dev tool synthesizing AI coding sessions into a browsable wiki. It defines five new phases (1.75 Agent Survey, 5.25 Adapter Flow, 6.5 Self-Demo, 7.5 Living Knowledge) and locks steering decisions (Python 3.12+, offline-first, privacy-first defaults, MIT license). The critical Phase 1.75 gates new adapters on three requirements: a compatibility matrix row, test fixtures with snapshot tests, and pinned schema versions. Adapters must gracefully degrade on unknown record types, skipping silently and logging only at DEBUG level while always preserving user content.

## Key Claims

- llmwiki extends "Open Source Project Framework v4.0" with 5 new phases (1.75, 5.25, 6.5, 7.5) tailored for agent-native tools that ingest AI session data
- Phase 1.75 (Agent Survey) requires every claimed agent to have a compatibility matrix row, test fixtures, and schema version constants; production adapters are gated on all three, shipping as "stubs" without them
- Adapters must gracefully degrade on unknown record types by silently skipping and logging only at DEBUG level, never dropping user prompts or assistant text
- llmwiki scored 22/25 on Phase 1 validation (above the 20+ build threshold), with personal fit as the lowest-scoring dimension at 4/5
- Steering decisions lock runtime floor at Python 3.12+ with stdlib + markdown, default to offline-first and privacy-first (no telemetry, redaction enabled, binding to 127.0.0.1), and forbid GPL/AGPL dependencies to maintain MIT compatibility

## Key Quotes

> "This document is both the **spec for how llmwiki is built** and the **contribution guide for anyone extending it**. It is the source of truth for what "done" means at each phase."
— Establishes the framework's dual purpose as technical specification and community contribution guidelines.

> "Agent-native tools need to know the `.jsonl` / session store schema for every agent they claim to support"
— Justifies Phase 1.75, ensuring adapters are tested before production release.

> "Without all three [matrix row, fixtures, schema versions], the adapter ships as a **stub** (imports cleanly, logs "not yet tested", does not convert)."
— Defines the gate between stub (untested) and production adapters.

> "Never drop user-visible content — user prompts and assistant text are always rendered even if the wrapping record is unknown"
— Core principle for graceful degradation; user content preservation takes precedence over schema completeness.

## Connections

- [[llmwiki]] (entity) — this framework spec defines the project's extended pipeline and governance
  - fact: Extends "Open Source Project Framework v4.0" with 5 new phases for agent-native tools
  - fact: Scored 22/25 on Phase 1 validation as of 2026-04-08

- [[Adapters]] (entity) — Phase 5.25 formalizes the community contribution contract with testing and compatibility requirements
  - fact: Production adapters require test fixtures, snapshot tests, and pinned schema version constants
  - fact: Adapters must gracefully degrade on unknown record types

- [[Claude Code]] (entity) — production-ready adapter with session store at `~/.claude/projects/<proj>/`
  - fact: Tested against version 2.1.87; supports user, assistant, tool_use, tool_result, queue-operation, file-history-snapshot, progress record types

- [[Codex CLI]] (entity) — stub adapter with session store schema details still to be confirmed (TBC)

- [[Wiki Synthesis]] (concept) — phases 6.5 (Self-Demo) and 7.5 (Living Knowledge) describe how synthesized wiki content drives adoption
  - fact: Self-Demo publishes the tool's own dev history as a public GitHub Pages site
  - fact: Living Knowledge loop treats the wiki as a growth engine updated on every release

- [[Schema-Versioning]] (concept) — cross-cutting rule for handling schema evolution and unknown record types across adapters
  - fact: Adapters pin `SUPPORTED_SCHEMA_VERSIONS` to declare compatibility boundaries
  - fact: Adapters must gracefully degrade on unknown record types without crashing or dropping user content