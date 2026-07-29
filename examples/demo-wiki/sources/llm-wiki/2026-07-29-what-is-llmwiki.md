---
title: "What is llmwiki"
type: source
tags: [raw-doc, demo, llmwiki, session-transcript, llm-wiki, knowledge-base, session-synthesis, static-site-generation, wiki-architecture]
date: 2026-07-29
source_file: raw/docs/llm-wiki/what-is-llmwiki.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

llmwiki is a three-layer system for converting coding-agent session transcripts into a searchable personal knowledge base: immutable raw transcripts, an agent-maintained wiki layer with cross-linked content, and a generated static site. It solves the problem of session context being buried in long conversations by making history queryable for both the current user and future agent sessions, without relying on third-party memory vaults.

## Key Claims

- llmwiki architecture has three distinct layers: `raw/` (immutable source of truth), `wiki/` (LLM-synthesized with cross-links), and `site/` (generated static HTML)
- Raw transcripts are never edited by hand once written and form the authoritative record of session history
- Session data remains local and self-hosted; optional web publishing does not require uploading to third-party services
- The system is designed to make session context queryable by both the current user and subsequent agent sessions
- Supported session sources include Claude Code, Cursor, Codex, OpenClaw, and other coding agents
- The public demo uses only synthetic and example content; no personal transcripts are published

## Key Quotes

> "llmwiki turns coding-agent session history into a Karpathy-style personal knowledge base: immutable raw transcripts, an LLM-maintained wiki layer, and a searchable static site."
— Core value proposition, combining persistence, agent synthesis, and discoverability

> "Long agent sessions bury decisions, tool choices, and project context. llmwiki makes that history queryable — by you and by the next agent session — without uploading a vault to a third-party memory product."
— Motivating problem and key architectural constraint

## Connections

- Inspired by personal knowledge management practices referenced as [[Karpathy]]-style