---
title: "Upgrade guide (part 1/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, upgrade-guide, breaking-changes, schema-migration, cli-exit-codes, link-rewrites]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This excerpt from the llmwiki upgrade guide documents three major unreleased breaking changes: discarded topic link rewrites (#282), changes to `add`/`wiki_add` synthesis behavior (#273), and new exit code handling for synthesis operations (#181). The guide provides migration commands, behavior flips, and updated API contracts that require user action during upgrade.

## Key Claims

- `candidates discard` now rewrites all links to discarded names as plain text or redirects them to an existing page via `--redirect`, with a `llmwiki migrate discarded-topic-links` command for offline cleanup (#282)
- `llmwiki add` and MCP `wiki_add` no longer synthesize by default; synthesis now requires explicit `--synthesize` flag (CLI) or `synthesize: true` (MCP), or a separate `llmwiki synth` run (#273)
- New exit code `75` indicates synthesis backend exhaustion of usage quota (Claude CLI, Cursor Agent CLI, or Ollama); this is distinct from rate-limit `429` (#181)
- `synth` now exits `130` on Ctrl+C interruption instead of `0`; a second Ctrl+C terminates backend processes immediately (#181)
- Merged candidates detected by the migration command print their inferred survivor page; rerunning with `--redirect` specifications points those links to the correct page and records aliases (#282)

## Key Quotes

> "Most releases are drop-in (…) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`."

Frames the upgrade guide as focusing on breaking changes, not routine updates.

> "`candidates discard` now turns every `[[link]]` to the discarded name into plain text (or, with `--redirect PAGE`, into `[[PAGE|text]]` plus a `## Aliases` entry on that page)"

Shows the link rewriting mechanism for handling removed topics.

> "**Default:** `llmwiki add` and MCP `wiki_add` write raw docs and rebuild the site; they do **not** create `wiki/sources/` pages."

Clarifies the behavior flip in PR #273 — synthesis is now opt-in, not automatic on add operations.

> "**New exit code `75`:** `synth` and `all` exit `75` when the synthesis backend (Claude CLI, Cursor Agent CLI or Ollama) reports an exhausted usage quota in its error message."

Documents new semantics for backend quota exhaustion, distinct from transient rate limits.

## Connections

- [[llmwiki]] (entity) — the project being upgraded between versions
  - fact: Upgrade path now includes optional migration to rewrite links to discarded topic names and behavior changes in add/synth APIs
- [[Wiki Synthesis]] (concept) — synthesis is now opt-in after add operations
  - fact: Scripts expecting automatic synthesis on `add` must be updated to either pass `--synthesize` or run `llmwiki synth` separately
- [[MCP Server]] (entity) — the `wiki_add` MCP command is affected by synthesis behavior change
  - fact: MCP clients must pass `synthesize: true` to trigger synthesis; default behavior writes raw docs only