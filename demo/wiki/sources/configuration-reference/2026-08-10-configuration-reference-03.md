---
title: "Configuration Reference (part 3/4)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, synthesis-backends, ingest-filters, cost-optimization]
date: 2026-08-10
source_file: 
project: configuration-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation excerpt defines the complete configuration namespace for [[LLM Wiki]], covering ingest filters, redaction, truncation, scheduling, adapter integrations, and [[Synthesis Backends]]. It emphasizes cost optimization through `claude_lean` (~9x reduction), effort tuning, and concurrency control, while documenting the removal of the legacy agent-delegate backend in v1.4.0 and the separation of timeout settings per backend.

## Key Claims

- The `exclude_headless` filter prevents synthesis feedback loops by skipping Agent-SDK sessions at both ingest and synthesis stages, ensuring headless output is never re-synthesized.
- The `claude_lean` setting (default `true`) reduces synthesis cost by ~9x by stripping agent scaffolding, tool schemas, and system prompts from each claude call.
- Extended thinking on Claude is billed at ~5x the input rate; on Haiku, default effort yields ~5,753 output tokens/page vs. ~1,609 at `low` effort, making `claude_effort: low` cost-effective on small models.
- The agent-delegate backend was removed in v1.4.0; `synthesis.backend` now explicitly chooses between `"dummy"`, `"ollama"`, or `"claude"`.
- Synthesis concurrency is bounded 1–16 (subprocess limit for the claude backend); out-of-range values clamp or warn rather than failing.

## Key Quotes

> "Prevents the synthesis feedback loop. Applies at **both** ingest (never converted) and synthesis (a headless session already in `raw/` is never synthesized and never counted as backlog)" — safeguard preventing Agent-SDK-generated sessions from being re-synthesized.

> "Strip agent scaffolding (tool schemas, MCP servers, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured." — quantified cost benefit of the `claude_lean` default.

> "The old `"agent"` / agent-delegate backend was removed in v1.4.0." — breaking change for users upgrading from earlier releases.

## Connections

- [[LLM Wiki]] — the main system whose configuration is fully documented here.
- [[Synthesis Backends]] — covers the `synthesis.*` section: backend selection (claude/ollama/dummy), model choice, effort tuning, concurrency limits, and cost optimization.

## Contradictions

None identified.