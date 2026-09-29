---
title: "Codex CLI adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, adapters-codex-cli, headless-filtering, schema-normalization, privacy-redaction]
date: 2026-09-28
source_file: 
project: adapters-codex-cli
model: 
last_updated: 2026-09-28
---
## Summary

This documentation describes the Codex CLI adapter, a core [[llmwiki]] module that reads OpenAI's Codex session transcripts from `~/.codex/sessions/` and `~/.codex/projects/` directories. The adapter auto-enables when these roots exist, derives project slugs from working directory metadata, normalizes Codex schema versions (v0.x, v1.0) into Claude-style record format, and applies the same privacy redaction as [[Claude Code]]. All Codex sessions are treated as interactive (non-headless).

## Key Claims

- Codex CLI is a Core adapter that auto-detects when `~/.codex/` source directories exist; no explicit `--adapter` flag is required to enable it.
- Project slugs are derived from the `cwd` field in the first session's metadata record, lowercased with spaces converted to dashes; if `cwd` is missing, the parent directory name is used as fallback.
- The adapter normalizes Codex-native record types (`response_item`, `event_msg`, etc.) into the shared Claude-style format used internally.
- Codex sessions lack verified automation-launch markers and are treated as interactive; they bypass headless filtering by default.
- Privacy redaction (API keys, tokens, emails, usernames) is inherited from the [[Claude Code]] adapter; additional Codex-specific patterns can be added via `redaction.extra_patterns`.

## Key Quotes

> "Core adapter — included on a bare `llmwiki sync` when either root exists. No `--adapter` flag required."

This documents the auto-detection behavior: users need not manually enable the adapter if source directories are present.

> "Codex has **no verified automation-launch markers** in the store today, so Codex sessions are treated as **not** headless."

This explains the design decision to classify Codex sessions as interactive by default.

> "Redaction is the same as for Claude Code — API keys, tokens, and emails are scrubbed at convert time, and home-path usernames too when `redaction.redact_username: true`."

This shows privacy handling reuses existing [[Claude Code]] infrastructure.

## Connections

- [[Adapters]] (entity) — framework for extracting and normalizing sessions from external tools
  - fact: Codex CLI adapter converts Codex-native record types to the shared Claude-style format.
- [[llmwiki]] (entity) — core system into which the Codex adapter ingests sessions
  - fact: Codex CLI is implemented as a Core adapter module (`llmwiki.adapters.codex_cli`) that auto-enables when roots exist.
- [[Claude Code]] (entity) — related adapter whose privacy redaction logic is reused for Codex sessions
  - fact: API key, token, email, and username scrubbing follow the same mechanisms as Claude Code.
- [[Multi-agent setup]] (concept) — framework for filtering headless vs. interactive sessions across multiple agent adapters
  - fact: Codex sessions are classified as interactive (non-headless) due to lack of automation markers.

## Contradictions

None identified.