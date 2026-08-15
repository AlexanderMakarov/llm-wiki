---
title: "ChatGPT adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, chatgpt-adapter, session-ingestion, conversation-export, json-parsing, configuration-opt-in, adapter-architecture]
date: 2026-08-10
source_file: 
project: chatgpt-adapter
model: 
last_updated: 2026-08-11
---
## Summary

The ChatGPT adapter enables ingestion of ChatGPT conversation exports into the wiki by parsing `conversations.json` and converting it into structured session documents. It is marked as an AI-session adapter but requires explicit opt-in configuration (unlike other session types) because the source file path is user-defined. The adapter linearizes conversation trees to exclude dead branches, preserves only text turns (dropping images/audio), and outputs to `raw/sessions/chatgpt/` with timestamped, slug-derived filenames.

## Key Claims

- The adapter parses the parent→child tree structure from ChatGPT exports and linearizes only the active conversation chain, discarding abandoned branches.
- Configuration via `sessions_config.json` requires explicit opt-in—if `enabled` is omitted, the adapter stays silent, because unlike other session types, there is no default path for `conversations_json`.
- Output files are named `raw/sessions/chatgpt/<YYYY-MM-DDTHH-MM>-chatgpt-<slug>.md`, where the slug is derived from the conversation title and sanitized to filesystem-safe characters.
- Re-exporting data from ChatGPT overwrites the old `conversations.json` file; users must manually re-sync after each export to capture new conversations, though the state file handles idempotency for unchanged ones.
- Image and audio modalities present in GPT-4o sessions are discarded; only text turns are retained.

## Key Quotes

> "Opt-in — the adapter is marked `is_ai_session = True` but **`default: no`** because the source file lives in a user-chosen path."

This explains the design rationale for requiring explicit configuration, differentiating it from other AI-session types.

> "Linearises the active chain (the one that made it to the final response) — no dead branches."

The core algorithm that reconstructs a single linear conversation from the branching message tree.

> "If `enabled` is omitted the adapter stays silent (AI-session-opt-in rule from #326 doesn't apply because the default `conversations_json` path is unknown — we need explicit opt-in)."

Documents the exception to the general AI-session-opt-in rule and its justification.

## Connections

- [[Adapters]] — this is one of several adapters (alongside Claude Code, Codex, Cursor session types) in the llm-wiki ecosystem for ingesting AI conversations.
- [[Session Documents]] — the adapter's output format, tagged with frontmatter and placed in the `raw/sessions/` directory.

## Contradictions

None identified.