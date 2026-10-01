---
title: "CLI reference (part 8/19: Auto-tagging (#351))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, auto-tagging, synthesize-command, frontmatter, tag-validation]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This documentation establishes the CLI interface for the `synth` command with detailed flags controlling synthesis behavior, candidate harvesting, and concurrency. It introduces the auto-tagging feature (#351) that automatically generates topical tags for wiki pages by parsing an LLM-produced `<!-- suggested-tags: ... -->` comment from synthesis responses. Auto-tags are merged with baseline tags (adapter, project slug, model family) while preserving maintainer-curated tags on `--force`, applying stop-word filters, capping at 5 AI tags per page, and rejecting near-duplicates at 0.80 similarity threshold.

## Key Claims

- The `--estimate` flag provides token and dollar cost projections for pending sources without executing synthesis
- The `--candidates-only` flag harvests entity/concept candidates by reading only already-synthesized source pages, incurring zero LLM cost and no per-source synthesis round-trip
- Auto-tagging produces a `<!-- suggested-tags: ... -->` HTML comment as the first line of the LLM response, which the pipeline parses, strips, and merges into frontmatter
- Tags added manually via `llmwiki tag add` are preserved at the front of the tag list when `--force` is used, allowing maintainers to override or prioritize their own curation
- A stop-word filter prevents the LLM from re-adding boilerplate tags (`session`, `summary`, `claude-code`, etc.)
- Auto-tagging is capped at 5 AI-generated tags per page to prevent topic drift
- Near-duplicate tag rejection uses a 0.80 similarity threshold plus prefix matching (e.g., blocking `prompt-cache` when `prompt-caching` is already present)

## Key Quotes

> "Every `synthesize` call now produces **topical** tags alongside the deterministic baseline. The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter with: **Baseline preserved** — adapter, project slug, model family stay. **Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list."

This establishes the core design principle: auto-tagging augments rather than replaces the baseline tag system and respects human curation priority.

> "Reads the source layer only — never `raw/` — so it runs no per-source synthesis and **no** classify LLM call; kind, description, and facts come from Connections topic bullets already on those pages. LLM cost is **zero**."

This explains the efficiency of `--candidates-only` by avoiding both re-synthesis and backend API calls entirely.

## Connections

- [[llmwiki]] (entity) — The system being documented; `synth` is its primary synthesis command.
  - fact: Auto-tagging rides the existing synthesis call without extra API cost.

- [[Wiki Synthesis]] (concept) — Auto-tagging is integrated into the synthesis pipeline as a post-processing step.
  - fact: The LLM produces suggested-tags as the first line of response, and the pipeline parses and merges them into frontmatter alongside synthesis body.

- [[Frontmatter]] (concept) — Topical tags are merged into page frontmatter metadata.
  - fact: Baseline tags (adapter, project slug, model family) are preserved alongside AI-generated tags; maintainer-added tags stay at the front on `--force`.

- [[Lint Rules]] (concept) — Tag validation rules (stop-word filter, near-dup rejection, 5-tag cap) enforce metadata integrity.
  - fact: Stop-word filter prevents boilerplate tags like `session`, `summary`, and `claude-code` from being re-added by the LLM.

## Contradictions

None identified. This is pure reference documentation.