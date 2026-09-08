---
title: "Synthesis cost — what you pay per page, and why (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, token-pricing, prompt-caching, model-pricing, llmwiki-synth, source-page-synthesis, agent-scaffolding]
date: 2026-09-08
source_file: 
project: reference-synthesis-cost
model: 
last_updated: 2026-09-08
---
## Summary

Part 1 of the synthesis-cost reference explains how `llmwiki synth` charges LLM backends: one amortised known-names call per run plus one call per queued source page, with harvest and promote adding no extra asks. It maps provider billing (input, cached input, cache write, output) to the shipped `model_pricing.csv` rate card and shows that default `claude -p` invocations carry roughly 35k input tokens of agent scaffolding versus ~700 with lean flags—so about 95% of default input cost is overhead the synthesis stdin/stdout path never uses.

## Key Claims

- `llmwiki synth` bills one amortised known-names ask per run (LLM backends only; Dummy / non-LLM skips it) plus one ask per queued source page; harvest and promote add none.
- Output tokens are priced at roughly 5× input per token, including hidden reasoning/thinking tokens, so a “thinking” model can cost more than a higher-list-price model that answers directly.
- A cache write costs more than fresh input (e.g. 1.25× for 5-minute TTL); reuse across pages is partial because each `claude -p` invocation is a separate process.
- The synthesis prompt itself is about 2,100 tokens (format rules, topic vocabulary, session body capped at 8 KB), but default `claude -p` measured ~35,081 input tokens versus ~700 with lean flags in a repo with several MCP servers configured.
- Cursor Agent CLI synthesis estimates use the same static `model_pricing.csv` as Claude, not live Agent CLI billing; unpublished Cursor model ids may use stand-in rows (e.g. Kimi K3) marked approximate in `source` / `notes`.

## Key Quotes

> "So on a default setup, **~95% of the input bill is scaffolding the task cannot use.**" — explains why synthesis cost documentation focuses on CLI wrapper overhead, not just the ~2,100-token source-page prompt.

> "A cache write costs *more* than fresh input." — grounds why prompt caching is not automatically cheaper for one-off or per-page synth calls.

## Connections

- [[llmwiki]] (entity) — documents per-page synthesis economics and the `model_pricing.csv` rate card shipped in the wheel (#210).
  - fact: Synth billing is one known-names ask per run plus one ask per source page on LLM backends only.
- [[Wiki Synthesis]] (concept) — `llmwiki synth` source-page generation is the primary per-page cost driver described here.
  - fact: Harvest and promote steps do not add LLM asks in this billing model.
- [[Claude Code]] (entity) — default `claude -p` wraps system prompt, tool schemas, MCP tools, CLAUDE.md, and skills around stdin prompts.
  - fact: Measured bare vs lean `claude -p` input tokens: 35,081 vs 700 in a multi-MCP repo.
- [[MCP Server]] (entity) — configured MCP server tool schemas contribute to unusable input scaffolding on default CLI runs.
- [[Cursor]] (entity) — `synthesis.backend: cursor_cli` cost estimates align to the static rate card, not live Cursor billing.
- [[Adapters]] (concept) — LLM vs non-LLM backend distinction determines whether known-names and per-page asks run at all.
