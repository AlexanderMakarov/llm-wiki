---
title: "Synthesis cost — what you pay per page, and why (part 3/3: What synth --estimate prices)"
slug: synthesis-cost-what-you-pay-per-page-and-why-03
project: synthesis-cost-what-you-pay-per-page-and-why
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/synthesis-cost.md"
content_sha256: ed5236ca5048181277ddb59f9410748ce57939433fbfde555435273a335e5a23
---

> Part 3 of 3 of **Synthesis cost — what you pay per page, and why** — What synth --estimate prices.

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

`llmwiki build --synthesize` makes one extra `claude` call to write the landing-page overview. It gets the same lean flags, and its model is `synthesis.overview_model` — defaulting to `haiku`, since writing three prose paragraphs from a JSON brief is the cheapest real task here and shows none of the `Connections` weakness that matters for source pages.

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
