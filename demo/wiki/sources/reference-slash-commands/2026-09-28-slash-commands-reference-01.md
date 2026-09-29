---
title: "Slash commands reference (part 1/4)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, vault-pipeline, cli-vs-slash, agent-kit, wiki-lint]
date: 2026-09-28
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-28
---
## Summary

This reference guide documents the 12 slash commands that form the vault pipeline and are distributed via `llmwiki install-agent-kit` for use in [[Claude Code]]. It provides a decision tree distinguishing when to invoke commands via CLI versus slash patterns, explains each command's purpose, and details the lint mechanism for wiki quality assurance.

## Key Claims

- Exactly 12 slash commands compose the vault pipeline (wiki-init, wiki-sync, wiki-ingest, wiki-synth, wiki-candidates, wiki-query, wiki-update, wiki-lint, wiki-graph, wiki-reflect, wiki-build, wiki-all) and are installed by `llmwiki install-agent-kit --dest PATH`.
- Slash commands should be used when output needs to feed back into an LLM turn for chaining and follow-up actions; the CLI should be used for scripted execution in CI/cron jobs or when output is for manual reading.
- Maintainer and AWOS delivery commands (/release, /fix-bug, /implement-feature) are not part of the vault pipeline and are excluded from the agent kit installation.
- Lint is the unified quality-checking mechanism for the wiki, with registered rules of varying severities (error, warning, info), rather than a separate eval subcommand.

## Key Quotes

> "Every `/wiki-*` command `llmwiki install-agent-kit` ships — what it does, what it runs under the hood, and a realistic invocation example. Use these inside **Claude Code**."

Establishes the scope of the reference and its intended use environment.

> "if the output is for *you* to read + act on manually, use the CLI. If the output should feed back into an LLM turn, use the slash — the model sees the full stdout and can chain into the next step."

Articulates the fundamental distinction between CLI and slash invocation patterns.

## Connections

- [[Claude Code]] (entity) — primary environment for executing vault pipeline slash commands
  - fact: All 12 slash commands are designed for use inside Claude Code.
- [[llmwiki]] (entity) — the wiki system that implements and distributes these commands
  - fact: Commands are shipped via `llmwiki install-agent-kit` and placed in an agent directory.
- [[Wiki Synthesis]] (concept) — the core workflow these commands implement
  - fact: wiki-synth and wiki-candidates commands are pipeline steps for converting raw sources to published wiki pages.
- [[Lint Rules]] (concept) — integrated quality assurance mechanism
  - fact: /wiki-lint checks frontmatter completeness, [[Wikilinks]] integrity, orphans, duplicate titles, stale pages, tag conventions, and page findability.
- [[Adapters]] (entity) — related to the ingestion pipeline
  - fact: wiki-ingest command handles importing files and folders into the raw vault directory.