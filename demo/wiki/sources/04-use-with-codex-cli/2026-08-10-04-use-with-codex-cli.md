---
title: "04 · Use with Codex CLI"
type: source
tags: [wiki-add, raw-doc, session-transcript, 04-use-with-codex-cli, multi-agent-queries, session-aggregation, adapter-setup]
date: 2026-08-10
source_file: 
project: 04-use-with-codex-cli
model: 
last_updated: 2026-08-11
---
## Summary

This tutorial demonstrates how to integrate [[Codex CLI]] sessions into [[llmwiki]] so that transcripts from multiple AI agents (Claude, Codex, and others) can be ingested into a single searchable wiki. It covers adapter verification, enabling the Codex CLI adapter via configuration, syncing sessions, and querying across agents—turning separate silos into a unified record.

## Key Claims

- [[llmwiki]] maintains an [[Adapters|adapter registry]] that can automatically discover and ingest sessions from multiple AI agents in parallel
- The `codex_cli` adapter reads session transcripts from `~/.codex/sessions/` and requires only a one-line config to enable
- Ingested sessions carry `model` metadata in frontmatter, allowing filtering by agent in the wiki's sessions index
- Cross-agent queries via `/wiki-query` search the unified `wiki/` tree without caring which agent produced each session
- A minimal daily workflow is: work in Codex, run `llmwiki sync`, then query across both Claude and Codex sessions

## Key Quotes

> "llmwiki's adapter registry pulls from every AI agent it recognises — your wiki becomes a unified view across agents." — Core motivation: preventing session silos

> "Because all sessions land in the same `wiki/` tree, `/wiki-query` doesn't care which agent produced what." — Explains why multi-agent queries work transparently

## Connections

- [[llmwiki]] — the CLI orchestrating multi-agent session ingestion
- [[Codex CLI]] — the external tool whose sessions are being integrated
- [[Adapters]] — the registry mechanism enabling support for multiple AI agents