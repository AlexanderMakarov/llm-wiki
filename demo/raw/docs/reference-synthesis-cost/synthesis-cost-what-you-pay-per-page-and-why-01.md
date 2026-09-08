---
title: "Synthesis cost — what you pay per page, and why (part 1/3)"
slug: synthesis-cost-what-you-pay-per-page-and-why-01
project: reference-synthesis-cost
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/synthesis-cost.md"
content_sha256: 0fd6618636ab9b2d36be2b366a1a9e72bcc7d76a15e33e3ce61ad61c7a26f026
---

> Part 1 of 3 of **Synthesis cost — what you pay per page, and why**.

# Synthesis cost — what you pay per page, and why

`llmwiki synth` bills **one amortised known-names ask per run** (LLM backends only — Dummy / `not is_llm` skips it) **plus one ask per queued source page**. Harvest and promote add none. This page explains what a source-page call actually costs, which parts of the bill are your data and which are overhead, and how the shipped defaults were chosen.

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

The rate card llmwiki prices against lives in [`llmwiki/model_pricing.csv`](../../llmwiki/model_pricing.csv), inside the package so it ships in the wheel (#210) — one row per model, with `aliases` mapping CLI names (`sonnet`, `claude-haiku-4-5-20251001`, `composer-2.5`, `cursor-grok-4.6-high`) onto pricing rows. Update that file when provider pricing changes; nothing else hardcodes rates.

Cursor Agent CLI (`synthesis.backend: cursor_cli`) estimates use the **same static rate card**, not live Agent CLI billing. Rows for Composer 2.5 / Grok 4.5 / Grok 4.6 (and Fast variants) come from [Cursor models & pricing](https://cursor.com/docs/models-and-pricing). When an id has no published per-token rate, a temporary stand-in may mirror **Kimi K3** list rates and must say so in the row's `source` / `notes` — that is an approximate estimate aid, not measured Cursor billing.

## Where the money actually goes

The synthesis prompt — format rules, topic vocabulary, and a session body capped at 8 KB — is about **2,100 tokens**. But by default the `claude` CLI wraps every call in a full coding-agent context: its system prompt, all built-in tool schemas, every configured MCP server's tools, auto-discovered `CLAUDE.md` files, and the skill listing.

None of that is reachable by a synthesis call. The backend passes a prompt on stdin and reads stdout; it never lets the model use a tool. Measured with a trivial one-line prompt, in a repo with several MCP servers configured:

| Configuration | Input tokens |
|---|---|
| `claude -p -` (bare) | **35,081** |
| `claude -p -` + lean flags | **700** |

So on a default setup, **~95% of the input bill is scaffolding the task cannot use.**
