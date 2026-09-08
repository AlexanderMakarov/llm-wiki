---
title: "Synthesis cost — what you pay per page, and why (part 3/3: Why the default model is Sonnet, not Haiku)"
slug: synthesis-cost-what-you-pay-per-page-and-why-03
project: reference-synthesis-cost
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/synthesis-cost.md"
content_sha256: 0fd6618636ab9b2d36be2b366a1a9e72bcc7d76a15e33e3ce61ad61c7a26f026
---

> Part 3 of 3 of **Synthesis cost — what you pay per page, and why** — Why the default model is Sonnet, not Haiku.

## Why the default model is Sonnet, not Haiku

Haiku is cheaper per token, and for the *extraction* half of a source page it is genuinely competitive. It degrades on the *judgment* half. Same prompt, same page, measured:

| | Summary / Key Claims | Connections (`[[wikilinks]]`) |
|---|---|---|
| Sonnet | Accurate; caught a factual inconsistency between what the transcript claimed and what the code did | Linked the project entity and the language — the scopes a reader browses by |
| Haiku | Accurate, effectively equivalent | Linked incidental libraries and coined lowercase-with-spaces pages, violating the TitleCase convention and the prompt's "significant scopes only" rule; missed the project entity |

That regression is not cosmetic. `## Connections` is the only part of a source page that feeds `llmwiki graph` and the backlink index, and the topic vocabulary derived from it is injected back into *every subsequent* synthesis prompt. Bad links compound.

Watch the output direction too. Haiku 4.5 runs with extended thinking by default, which is billed as output:

| Configuration | Output tokens | $/page |
|---|---|---|
| Haiku, lean, default thinking | 4,278 | $0.028 |
| Haiku, lean, `MAX_THINKING_TOKENS=0` | 378 | $0.009 |
| Sonnet, lean | 730 | $0.042 |

Haiku's headline rate is ~3x cheaper than Sonnet's, but with thinking left on it only saved ~33% — the reasoning tokens ate the advantage.

**Recommendation:** keep `claude_model: "sonnet"` (the default). The lean flags already removed the dominant cost, and what remains buys measurably better graph structure. If your corpus is large and you accept weaker `Connections`, set `claude_model` to a Haiku id *and* `MAX_THINKING_TOKENS=0` — otherwise you pay for reasoning you did not want.

## What `synth --estimate` prices

`--estimate` prices exactly what the backend sends, per page:

```
(per-call overhead + prompt template + body) x input rate
                                   + completion x output rate
```

with no shared cached prefix — each page is its own process, so cost is linear in page count. The report splits the fixed part so a surprising number is traceable:

```
Per page: 5,288 tok fixed (890 agent overhead + 4,398 prompt) + body, ~800 out
```

A large `prompt` figure means the injected topic vocabulary has grown — it is re-sent on every call, and on a mature wiki it is usually the single biggest fixed cost per page, larger than the lean scaffolding. With `claude_lean` off, the overhead column jumps to ~35,000 and the report adds a warning.

`--estimate` never calls the API. It uses the rate card in `model_pricing.csv` plus a chars-per-token heuristic, so treat it as ±20%; on a real corpus the modelled figure came out ~10% under the measured one ($0.038 vs $0.042 per page).

### Corrections landed with this model (#57)

The previous estimator was wrong in four independent ways, each verified against `--output-format json`:

| Error | Effect |
|---|---|
| Priced a cached prefix of `CLAUDE.md` + `index.md` + `overview.md` | Billed ~32k tokens per page that the backend never sends, while ignoring the scaffolding and template it does |
| Assumed 1 cache write + N−1 cache hits | No prefix is shared across processes, so the discount never existed |
| Counted tokens at 4 chars/token | Transcripts run ~2.05 chars/token — a ~2x undercount |
| Priced input at the fresh `input` rate | It is billed as a 1-hour cache **write** at 2x, on every page |
| Assumed an 800-token completion | Real pages average ~1,372 |
| Counted full bodies, one call per doc | Bodies are truncated to 8,000 chars, and multi-part docs cost one call *per chunk* |

The rate card was wrong too: `sonnet-5` was listed at $2/$10 per MTok. Derived from `modelUsage.costUSD` (905 input + 494 output = $0.010125) the real figures are **$3/$15**. `haiku-4.5` at $1/$5 checked out.

The API-cache path in [`prompt-caching.md`](prompt-caching.md) is unaffected — a prefix genuinely is cached and re-read there.

## The site overview call

`llmwiki build --synthesize` makes one extra LLM call to write the landing-page overview when the active synthesis backend is an LLM (`claude`, `cursor_cli`, `ollama`). With `claude` it gets the same lean flags, and its model is `synthesis.overview_model` — defaulting to `haiku`, since writing three prose paragraphs from a JSON brief is the cheapest real task here and shows none of the `Connections` weakness that matters for source pages. With `dummy` (or an unavailable backend) the overview LLM is skipped — spend nothing (#230).

## Reproduce these numbers

`--output-format json` returns the real `usage` block, so you never have to trust an estimate:

```bash
echo "Say OK." | claude -p - --model sonnet --output-format json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['usage'], d['total_cost_usd'])"
```

Re-run with the lean flags from the table above to see the difference on your own machine — the scaffolding total depends on how many MCP servers and skills you have configured, so your baseline may be higher than 35k.

## Connections

- [`configuration.md` § Synthesis backend](../configuration.md#synthesis-backend) — selecting and configuring a backend
- [`configuration-reference.md`](../configuration-reference.md) — every `synthesis.*` key
- [`reference/prompt-caching.md`](prompt-caching.md) — the cache-block plumbing and the batch API
- [`reference/cli.md`](cli.md) — `synth --check` / `--estimate`
