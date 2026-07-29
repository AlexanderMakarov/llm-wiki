---
title: "What is llmwiki"
slug: what-is-llmwiki
project: llm-wiki
type: source
tags: [raw-doc, demo, llmwiki]
date: 2026-07-29
source: examples/demo-docs/llm-wiki/what-is-llmwiki.md
---

# What is llmwiki

**llmwiki** turns coding-agent session history into a Karpathy-style personal knowledge base: immutable raw transcripts, an LLM-maintained wiki layer, and a searchable static site.

## Three layers

1. **`raw/`** — Source of truth. Session transcripts (from Claude Code, Cursor, Codex, OpenClaw, …) and added documents. Never edit by hand once written.
2. **`wiki/`** — Agent-owned synthesis: source summaries, entities, concepts, index, overview, log. Cross-linked with `[[wikilinks]]`.
3. **`site/`** — Generated HTML from `llmwiki build`. Browse locally with `llmwiki serve` or publish (for example GitHub Pages).

## Why it exists

Long agent sessions bury decisions, tool choices, and project context. llmwiki makes that history queryable — by you and by the next agent session — without uploading a vault to a third-party memory product.

## This public demo

The GitHub Pages demo is built from synthetic sessions under `examples/demo-sessions/`, product docs under `examples/demo-docs/`, and fixture MCP usage under `examples/demo-usage/`. No personal transcripts are published.
