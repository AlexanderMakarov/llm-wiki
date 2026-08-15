---
title: "CLI reference (part 6/8: synthesize — deprecated alias for synth --sources-only)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, queue-management, state-migration, username-redaction, tool-expansion]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation covers five [[llmwiki]] CLI commands: the deprecated `synthesize` alias (retained for backward compatibility), the `queue` command for managing the unified vault task queue, and three migration utilities for v1.4.0+ upgrades (`migrate-state`, `migrate-raw-redaction`, `migrate-tools-used`).

## Key Claims

- `synthesize` is a deprecated alias for `synth --sources-only` kept for backward compatibility; it always prints a deprecation warning and defaults to sources-only mode
- The unified `queue` command manages a `llmwiki-state.json`-backed task queue with four task types: `add_doc`, `session_sync`, `synthesize`, and `build`
- `migrate-state` is idempotent and performs vault repairs including resolving pending prompts, purging dead synth_request items, enqueueing synthesis tasks, and warning about removed synthesis backends
- `migrate-raw-redaction` performs in-place string rewriting of usernames in `raw/` files without triggering re-sync or re-synthesis
- `migrate-tools-used` expands `CallMcpTool` entries in already-synced raw sessions by re-reading from origin session stores; it never invents MCP names when the origin is unavailable

## Key Quotes

> "Always prints a deprecation warning and defaults to sources-only (does **not** harvest candidates unless you pass `--candidates-only`)" — establishes that `synthesize` is truly deprecated but backward-compatible

> "Private local vaults that never publish `raw/` can skip this and only run `llmwiki build` after upgrading" — migration commands are optional for non-publishing configurations

> "Missing origins leave `CallMcpTool` entries intact for `wiki_adoption` body fallback" — safety guarantee that tool-expansion gracefully degrades when origin sessions are unavailable

## Connections

- [[llmwiki]] — this documents the core CLI command set for the tool
- [[Vault Queue]] — the `queue` command is the primary interface for the unified task queue system  
- [[State Migration]] — three commands handle upgrading vault state across versions

## Contradictions

None apparent in this documentation.