---
title: "Synthesis cost — what you pay per page, and why (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, llm-pricing, prompt-caching, token-efficiency]
date: 2026-09-07
source_file: raw/docs/reference-synthesis-cost/synthesis-cost-what-you-pay-per-page-and-why-01.md
project: reference-synthesis-cost
model: 
last_updated: 2026-09-07
---
## Summary

This reference document explains the actual token costs of `llmwiki synth`. It establishes that synthesis bills one "amortised known-names ask" per run plus one per queued source page, defines how LLM providers price tokens (output ~5x input), and reveals the central inefficiency: default `claude` CLI configurations wrap synthesis in ~35,000 tokens of unused scaffolding—95% overhead on a task that never invokes tools or MCP servers.

## Key Claims

1. `llmwiki synth` bills one "amortised known-names ask" per run plus one per queued source page (LLM backends only; Harvest and Promote add no cost)
2. Output tokens cost approximately 5x the price of input tokens, so thinking-based models can be more expensive than direct-answer models even at lower headline rates
3. The default `claude -p -` invocation wraps synthesis in ~35,081 tokens of scaffolding (system prompt, tool schemas, MCP servers, CLAUDE.md files), reducible to ~700 with lean flags—a ~95% waste on a task that never uses tools
4. Cached input tokens cost 0.1x fresh input; cache write costs 1.25–2x, so caching only justifies itself if the same prefix is re-read multiple times across separate invocations
5. The synthesis prompt itself is ~2,100 tokens but is dwarfed by CLI scaffolding overhead in default setups

## Key Quotes

> "Output is the expensive direction — roughly 5x input per token. A model that "thinks" before answering can cost more than a pricier model that answers directly, even at a lower headline rate." — The core economic driver: reasoning tokens are expensive.

> "None of that is reachable by a synthesis call. The backend passes a prompt on stdin and reads stdout; it never lets the model use a tool." — Why CLI scaffolding is wasted on synthesis.

> "So on a default setup, **~95% of the input bill is scaffolding the task cannot use.**" — The critical inefficiency measured and revealed.

## Connections

- [[llmwiki]] (project) — the wiki synthesis system whose cost structure is analyzed here
  - fact: billing is one call per run + one per queued source page (LLM backends only)
  - fact: rate card lives in `model_pricing.csv` and ships in the wheel

- [[prompt-caching]] (concept) — token rate type enabling cost reduction through cache hits
  - fact: cached input costs 0.1x fresh input; cache write costs 1.25–2x (5-min or 1-hour TTL)
  - fact: caching breaks even only if the same prefix is re-read, which is limited in separate `claude -p` invocations

## Contradictions

None identified.