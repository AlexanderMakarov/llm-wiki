---
title: "CLI reference (part 7/15)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, suggested-tags, topical-tagging, wiki-synthesis, frontmatter-tags, cli-synth, tag-merge, synth-cli]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

Part 7 of the CLI reference documents how synthesis attaches **topical** tags to wiki source pages: the synthesizer’s first line is a `<!-- suggested-tags: ... -->` comment, which the pipeline parses, strips from the body, and merges with deterministic baseline tags. Merge rules preserve adapter/project/model tags, respect maintainer tags on `--force`, filter stop-words, cap at five AI tags, and reject near-duplicates. The behavior adds no extra API call beyond the existing synthesis request. The doc also notes removal of the `synthesize` and `consolidate-topics` commands in favor of `synth`.

## Key Claims

- Every synthesis response can include a `<!-- suggested-tags: ... -->` block as its first line; the pipeline parses it, removes it from page body, and merges the listed tags into frontmatter.
- Baseline tags (adapter, project slug, model family) are always preserved; tags added with `llmwiki tag add` stay at the front when synthesis runs with `--force`.
- AI-suggested tags are limited to five per page, filtered against a stop-word list (e.g. `session`, `summary`, `claude-code`), and near-duplicates are rejected (similarity threshold 0.80 plus prefix checks, e.g. blocking `prompt-cache` when `prompt-caching` exists).
- Tag suggestion uses the same synthesis API call as page content, so `--estimate` cost is unchanged; if no suggested-tags block is returned, the page still gets baseline tags only.
- The CLI no longer exposes `synthesize` (use `synth`; the old name implied sources-only by default) or `consolidate-topics` (known-names preparation is part of `synth`).

## Key Quotes

> "No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged."

> "**Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list."

> "Removed: `synthesize` (use `synth`; the old name was sources-only by default) and `consolidate-topics` (known-names prepare is part of `synth`)."

## Connections

- [[llmwiki]] (entity) — CLI and pipeline that parse suggested-tags and merge them into wiki source frontmatter.
  - fact: Topical tag merge is implemented in the synthesis pipeline without a separate tagging API call.
- [[Wiki Synthesis]] (concept) — Automated pass that produces source pages and now emits searchable topical tags alongside deterministic metadata.
  - fact: Suggested tags ride the same synthesizer response as page body content.
- [[Adapters]] (concept) — Adapter identity remains in baseline tags and is excluded from LLM re-suggestion via stop-word filtering.
- [[Wikilinks]] (concept) — Distinct from tags; this session is about frontmatter tag policy for source pages, not link resolution.
