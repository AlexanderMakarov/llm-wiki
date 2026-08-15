---
title: "Claude CLI synthesis backend"
type: source
tags: [wiki-add, raw-doc, session-transcript, claude-cli-synthesis-backend, cli-integration, state-migration]
date: 2026-08-10
source_file: 
project: claude-cli-synthesis-backend
model: 
last_updated: 2026-08-11
---
## Summary

v1.4.0 of [[LLMWiki]] introduces a simplified synthesis backend using the [[Claude CLI]] (`claude -p -`) for synchronous, agent-friendly page synthesis. Each page is synthesized with a single CLI invocation, eliminating pending-prompt files and the previous `--list-pending`/`--complete` round-trip workflow. Configuration is minimal (backend name and model), and the backend is strictly required—failed invocations abort rather than silently falling back.

## Key Claims

- v1.4.0 replaces `synthesis.backend: agent` / `agent_delegate` with `synthesis.backend: claude`
- Each page is synthesized via single `claude -p -` invocation; no intermediate pending-prompt files or `--list-pending`/`--complete` round-trips
- State from `.llmwiki-pending-prompts/` is migrated to `llmwiki-state.json` (one-time upgrade step)
- Configuration is minimal: requires `synthesis.backend: "claude"` and `synthesis.claude_model`; optionally `claude_path` and `timeout`
- Single backend instance serves multiple synthesis modes: `sync` auto-paths, `synthesize`, `add`, and `all --with-synth`
- Works with or without `ANTHROPIC_API_KEY`, using Claude Code CLI subscription as fallback
- Unavailable backend aborts the run—no silent fallback to dummy page writes

## Key Quotes

> "synchronous `claude -p` synthesis" — describes the architectural shift from agent-based async to CLI-based sync

> "no pending-prompt files, no `--list-pending` / `--complete` round-trip" — core operational simplification vs. previous workflow

> "Unavailable backend aborts the run (no silent dummy overwrite of real pages)" — critical invariant: synthesis failures are not masked

## Connections

- [[LLMWiki]] — the synthesis tool and project this backend implements
- [[Claude CLI]] — the invocation mechanism underlying synthesis