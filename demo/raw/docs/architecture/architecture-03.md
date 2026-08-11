---
title: "Architecture (part 3/3: Adding an adapter)"
slug: architecture-03
project: architecture
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/architecture.md"
content_sha256: f9d60b3a6d2545eb672aff3ec89271d5d5daf460c4cf2aa42001fe5d6fdfe471
---

> Part 3 of 3 of **Architecture** — Adding an adapter.

## Adding an adapter

See [framework.md §5.25 Adapter Flow](framework.md) for the full contract. TL;DR: one new file at `llmwiki/adapters/<agent>.py`, one fixture, one snapshot test, one doc page, one README line, one CHANGELOG entry.

## Design principles

1. **Stdlib first.** Runtime dep: `markdown` only. Nothing else. Syntax highlighting runs client-side via a CDN-loaded highlight.js (v0.5, #73) so the build stays deterministic and offline-capable.
2. **Privacy by default.** Redact everything sensitive before it hits disk.
3. **Idempotent everything.** Re-running any command is safe and cheap.
4. **Localhost only.** No network, no telemetry, no cloud. The user controls if/when to publish.
5. **One file per concern.** build.py is one file, not a folder of templates. The whole HTML rendering lives there including CSS + JS.
6. **Agent-agnostic core.** `convert.py` doesn't know which agent produced the .jsonl. Adapters translate.
