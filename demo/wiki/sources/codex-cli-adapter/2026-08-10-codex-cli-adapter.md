---
title: "Codex CLI adapter"
type: source
tags: [wiki-add, raw-doc, session-transcript, codex-cli-adapter, adapter-development, snapshot-testing, jsonl-format, session-store-discovery]
date: 2026-08-10
source_file: 
project: codex-cli-adapter
model: 
last_updated: 2026-08-11
---
## Summary

This document defines the v0.1 stub status of the Codex CLI adapter for [[LLM-Wiki]], which can import and register but lacks production-ready record parsing and test fixtures. The document outlines an explicit 8-step workflow to graduate the adapter to production, centered on creating real session fixtures, comparing the record format against [[Claude-Code]], and validating with snapshot tests.

## Key Claims

- Codex CLI adapter v0.1 registers cleanly and declares its session store path, but does not parse records correctly or have tested snapshot fixtures
- Production readiness requires 2–3 real session fixtures (each <50 KB), redacted and placed in `tests/fixtures/codex_cli/`
- Codex session stores are expected at `~/.codex/sessions/` or `~/.codex/projects/<project>/`, checked in fallback order
- Codex record format is expected to mirror [[Claude-Code]]'s `.jsonl` format (user/assistant/tool_result message types), but divergences will require a custom record classifier
- Session redaction and privacy handling use the same converter-layer mechanism as other adapters; no Codex-specific redaction rules are documented yet

## Key Quotes

> "If you run `llmwiki sync` with Codex installed, the stub will attempt to use the shared converter with the default record-type filters. Your mileage may vary. The output is best-effort."

Clarifies that the stub is functional but unreliable until production finalisation.

> "llmwiki's Phase 5.25 Adapter Flow applies. To push this adapter to production: [8-step process]"

Establishes the formal workflow for graduation from stub to stable release.

## Connections

- [[LLM-Wiki]] — Codex adapter is part of the core session ingestion architecture
- [[Claude-Code]] — record format baseline and output comparison target
- `tests/fixtures/codex_cli/` — where real session samples are stored during development
- `tests/snapshots/codex_cli/` — where expected output is validated

## Contradictions

None identified.