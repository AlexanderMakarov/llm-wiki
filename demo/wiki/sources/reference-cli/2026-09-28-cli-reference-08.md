---
title: "CLI reference (part 8/19: Auto-tagging (#351))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, auto-tagging, synthesis-modes, tag-deduplication, backend-selection]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

Part 8 of the CLI reference documents the `synthesize` (aka `synth`) command's flags, backends, and new auto-tagging feature (#351). Auto-tagging automatically generates topical tags from synthesis output with stop-word filtering, deduplication, and maintainer override—riding the existing synthesis call at no extra API cost. The reference also describes multiple synthesis modes (sources-only, sessions-only, docs-only, candidates-only) and configurable backends (dummy, ollama, claude, cursor_cli).

## Key Claims

- Auto-tagging emits a `<!-- suggested-tags: ... -->` block as the first line of synthesis output, which the pipeline parses and merges into frontmatter with stop-word filtering and near-dup rejection (0.80 similarity threshold).
- Maintainer-added tags are preserved at the front of the tag list when `--force` re-synthesizes a page.
- Maximum 5 AI-generated tags per page to prevent tag drift; boilerplate tags (e.g., `session`, `summary`, `claude-code`) are blocked by stop-word filter.
- Auto-tagging incurs no extra API cost because the suggested-tags block rides the existing synthesis call.
- The `--candidates-only` mode harvests entity/concept candidates from already-synthesized pages with zero LLM cost, reading only the source layer.
- Multiple synthesis modes are available with different cost and scope profiles: `--sources-only`, `--sessions-only`, `--docs-only`, and `--candidates-only`.
- Synthesis backend is configurable: `dummy`, `ollama`, `claude`, or `cursor_cli`, settable via `synthesis.backend` in config or `--backend` flag.
- Old `synthesize` command renamed to `synth`; `consolidate-topics` command removed.

## Key Quotes

> "No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged."
> — Why auto-tagging incurs no additional cost.

> "Maintainer wins — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list."
> — How user-curated tags are preserved during re-synthesis.

> "LLM cost is **zero**."
> — The `--candidates-only` mode processes already-synthesized pages without LLM inference.

## Connections

- [[llmwiki]] (entity) — The wiki system whose synthesis CLI is documented here.
  - fact: The synthesize/synth command auto-generates topical tags as part of standard output.
  - fact: Multiple backends (ollama, claude, cursor_cli) are configurable for synthesis runs.

- [[Wiki Synthesis]] (concept) — The synthesis process enhanced with automatic tagging and multiple synthesis modes.
  - fact: Auto-tagging filters boilerplate tags, deduplicates near-matches at 0.80 threshold, and caps tags at 5 per page.
  - fact: Candidates-only mode harvests entity/concept candidates with zero LLM cost from already-synthesized pages.

- [[Ollama]] (entity) — Local LLM runtime available as a synthesis backend.
  - fact: Selectable via `--backend ollama` or `synthesis.ollama` configuration block.

- [[Cursor]] (entity) — AI-enhanced code editor with Agent CLI usable for synthesis.
  - fact: Cursor Agent CLI available as `cursor_cli` backend with default model `composer-2.5`.