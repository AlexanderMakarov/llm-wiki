---
title: "CLI reference (part 7/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, tag-deduplication, suggested-tags, synthesis-integration, stop-word-filter]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-07.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This session documents part 7 of the [[Codex CLI]] reference, covering tag management behavior in the wiki system. It describes how baseline tags are always preserved, manually-added tags take priority with `--force`, a stop-word filter blocks boilerplate suggestions, and near-duplicate tags are rejected via similarity matching. Tag suggestion integrates into the synthesis call without additional API cost, and removed commands (`synthesize`, `consolidate-topics`) are superseded by `synth`.

## Key Claims

- Baseline tags (adapter, project slug, model family) are always preserved during tag operations
- Maintainer-added tags via `llmwiki tag add` remain at the front of the list when `--force` is used
- A stop-word filter prevents the LLM from re-suggesting boilerplate tags (`session`, `summary`, `claude-code`, etc.)
- Maximum of 5 AI-suggested tags per page to prevent tag drift
- Near-duplicate tags are rejected using 0.80 similarity threshold plus prefix matching (e.g., `prompt-cache` blocked when `prompt-caching` exists)
- Tag suggestion integrates into the synthesis call with no additional API round-trip cost
- Pages receive baseline tags even if the backend fails to return suggested-tags
- The `synthesize` command was removed in favor of `synth`
- The `consolidate-topics` command was removed; its functionality is integrated into `synth`

## Key Quotes

> "Maintainer wins — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list." — Demonstrates how the system prioritizes human curation over automated suggestions.

> "Stop-word filter — the LLM can't re-add boilerplate tags (`session`, `summary`, `claude-code`, etc.)." — Explains the filtering mechanism that prevents noise in tag suggestions.

> "Near-dup rejection — `prompt-cache` is blocked when `prompt-caching` is already on the page (threshold 0.80 + prefix check)." — Concrete example of tag deduplication behavior.

> "No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged." — Shows how tag suggestion is cost-efficient by integrating with synthesis.

## Connections

- [[Codex CLI]] (entity) — The command-line tool whose tag handling behavior is documented
  - fact: Tag management includes baseline preservation, maintainer priority, stop-word filtering, and deduplication
- [[llmwiki]] (entity) — The wiki system managed by the CLI
  - fact: Uses intelligent tag suggestion with multiple safeguards to prevent tag drift and noise
- [[Wiki Synthesis]] (concept) — The synthesis process that generates suggested tags
  - fact: Tag suggestion integrates into the synthesis call without additional API cost

## Contradictions

None identified.