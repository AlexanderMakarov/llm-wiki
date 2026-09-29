---
title: "Architecture (part 3/3: Design principles)"
slug: architecture-03
project: architecture
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/architecture.md"
content_sha256: 2bd3b154da7e9af93b24c396f171de63229075237be0402eb58bbb79eb5f9688
---

> Part 3 of 3 of **Architecture** — Design principles.

## Design principles

1. **Stdlib first.** Runtime dep: `markdown` only. Nothing else. Syntax highlighting runs client-side via a CDN-loaded highlight.js (v0.5, #73) so the build stays deterministic and offline-capable.
2. **Privacy by default.** Redact everything sensitive before it hits disk.
3. **Idempotent everything.** Re-running any command is safe and cheap.
4. **Localhost only.** No network, no telemetry, no cloud. The user controls if/when to publish.
5. **One file per concern.** build.py is one file, not a folder of templates. The whole HTML rendering lives there including CSS + JS.
6. **Agent-agnostic core.** `convert.py` doesn't know which agent produced the .jsonl. Adapters translate.
