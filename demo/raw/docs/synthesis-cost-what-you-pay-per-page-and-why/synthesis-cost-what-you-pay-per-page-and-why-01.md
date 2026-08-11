---
title: "Synthesis cost — what you pay per page, and why (part 1/3)"
slug: synthesis-cost-what-you-pay-per-page-and-why-01
project: synthesis-cost-what-you-pay-per-page-and-why
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/synthesis-cost.md"
content_sha256: ed5236ca5048181277ddb59f9410748ce57939433fbfde555435273a335e5a23
---

> Part 1 of 3 of **Synthesis cost — what you pay per page, and why**.

# Synthesis cost — what you pay per page, and why

`llmwiki synth` calls an LLM once per source page. This page explains what a call actually costs, which parts of the bill are your data and which are overhead, and how the shipped defaults were chosen.

Everything below is measured against the real `source_page.md` prompt via `claude -p - --output-format json`, which returns a `usage` block. Reproduce any row yourself with the recipe at the bottom.

## How LLM pricing works

Providers bill per **million tokens** (MTok), at different rates for each direction. A token is roughly 4 characters of English prose — the estimator in `llmwiki/cache.py` uses exactly that heuristic (`CHARS_PER_TOKEN = 4`).

| Rate | What it covers | Typical relative price |
|---|---|---|
| `input` | Fresh prompt tokens the model has not seen before | 1x (baseline) |
| `cached_input` | Prompt tokens served from a prompt cache hit | 0.1x |
| `cache_write` | First-time write of a prompt prefix into the cache | 1.25x (5-minute TTL) or 2x (1-hour TTL) |
| `output` | Tokens the model generates, **including hidden reasoning/thinking tokens** | 5x |

Two consequences drive every decision on this page:

1. **Output is the expensive direction** — roughly 5x input per token. A model that "thinks" before answering can cost more than a pricier model that answers directly, even at a lower headline rate.
2. **A cache write costs *more* than fresh input.** Caching only pays off if the same prefix is re-read. Each `claude -p` invocation is a separate process, so cache reuse across pages is partial at best.

The rate card llmwiki prices against lives in [`model_pricing.csv`](https://github.com/Pratiyush/llm-wiki/blob/master/model_pricing.csv) at the repo root — one row per model, with `aliases` mapping CLI names (`sonnet`, `claude-haiku-4-5-20251001`) onto pricing rows. Update that file when provider pricing changes; nothing else hardcodes rates.

## Where the money actually goes

The synthesis prompt — format rules, topic vocabulary, and a session body capped at 8 KB — is about **2,100 tokens**. But by default the `claude` CLI wraps every call in a full coding-agent context: its system prompt, all built-in tool schemas, every configured MCP server's tools, auto-discovered `CLAUDE.md` files, and the skill listing.

None of that is reachable by a synthesis call. The backend passes a prompt on stdin and reads stdout; it never lets the model use a tool. Measured with a trivial one-line prompt, in a repo with several MCP servers configured:

| Configuration | Input tokens |
|---|---|
| `claude -p -` (bare) | **35,081** |
| `claude -p -` + lean flags | **700** |

So on a default setup, **~95% of the input bill is scaffolding the task cannot use.**
