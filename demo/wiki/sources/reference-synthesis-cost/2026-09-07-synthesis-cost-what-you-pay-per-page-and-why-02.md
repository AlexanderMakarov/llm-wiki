---
title: "Synthesis cost — what you pay per page, and why (part 2/3: The lean flags)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, prompt-caching, cost-optimization, model-selection, token-efficiency]
date: 2026-09-07
source_file: raw/docs/reference-synthesis-cost/synthesis-cost-what-you-pay-per-page-and-why-02.md
project: reference-synthesis-cost
model: 
last_updated: 2026-09-07
---
## Summary

This reference documentation explains the cost optimization strategy for wiki synthesis in [[llmwiki]]. The system uses "lean flags" to reduce per-page synthesis cost by approximately 9x ($0.369 → $0.042 on a demo page; mean $0.0763 across 29 real pages) by stripping unnecessary tool schemas and configuration scanning, paired with [[prompt-caching]] that yields an additional ~25% steady-state reduction by placing the run-stable template half in the system prompt for 1-hour reuse. Claude Sonnet is recommended over Haiku despite higher per-token cost because it produces better `Connections` links, which feed the [[Knowledge Graph]] and backlink index used in future synthesis prompts.

## Key Claims

- Lean flags in `ClaudeCLISynthesizer` reduce per-page synthesis cost by ~9x with no change to output quality or the prompt contract; the argv order is load-bearing and pinned by test coverage.
- Prompt caching via system-prompt placement saves an additional ~25% on steady-state pages by reusing the run-stable template half across invocations ($0.092 cold → $0.057 warm).
- Vocabulary size was increased 80→200 because the run-stable prefix now rides in the cached prompt; this eliminates the token-budget justification for preventing graph fragmentation from re-coined topics.
- Claude Sonnet produces higher-quality connections than Haiku (correct TitleCase, project-scope entities, proper wikilink conventions); Haiku's extended-thinking tokens reduce the savings advantage to ~33% despite 3x cheaper per-token rate.
- Template splitting via `split_prompt_template()` in `llmwiki/synth/base.py` is backend-agnostic; each provider (Claude CLI, Ollama, Anthropic API, OpenAI/OpenRouter) caches the stable prefix in its mechanism (system prompt, KV-cache field, cache_control breakpoint, or leading message).

## Key Quotes

> "~9x cheaper, with no change to the prompt or the output contract." — establishes lean flags as a pure cost optimization without quality regression

> "Bad links compound." — explains why Haiku's weaker connections matter; poor wikilinks propagate through the knowledge graph and affect all downstream synthesis prompts

> "The remaining write is the page body, which is genuinely unique and cannot be cached." — sets realistic expectations for additional caching savings after lean flags

> "Keep `claude_model: "sonnet"` (the default). The lean flags already removed the dominant cost, and what remains buys measurably better graph structure." — integrates both optimization strategies into a coherent recommendation

## Connections

- [[llmwiki]] (project) — the wiki synthesis system being cost-optimized
  - fact: Lean flags are implemented in `ClaudeCLISynthesizer` (llmwiki/synth/claude_cli.py); the argv order is load-bearing and pinned by `test_lean_tools_flag_is_followed_by_a_flag`
  - fact: Template splitting happens in `split_prompt_template()` (llmwiki/synth/base.py) and is the backend-agnostic caching mechanism
  - fact: The quality of `Connections` links directly affects the knowledge graph fed back into future synthesis prompts

- [[prompt-caching]] (technique) — the cost-reduction strategy through template placement and reuse
  - fact: The system prompt (run-stable half) is cached for 1 hour and reused across CLI invocations
  - fact: Different backends implement caching differently: Claude CLI uses `--system-prompt`; Ollama uses the `system` field; Anthropic API uses `cache_control` breakpoints; OpenAI/OpenRouter use leading system messages with automatic prefix caching

- [[Knowledge Graph]] (system) — why synthesis output quality has cascading impact
  - fact: The `Connections` section is the only part of source pages that feeds the knowledge graph and backlink index
  - fact: Low-quality connections (lowercase-with-spaces non-conventions, incidental libraries) cascade through backlink generation and degrade future synthesis prompts

## Contradictions

None detected.