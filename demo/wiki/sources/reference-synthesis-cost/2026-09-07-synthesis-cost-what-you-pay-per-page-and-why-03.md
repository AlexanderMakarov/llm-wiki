---
title: "Synthesis cost — what you pay per page, and why (part 3/3: What synth --estimate prices)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, api-pricing, cost-estimation, rate-card]
date: 2026-09-07
source_file: raw/docs/reference-synthesis-cost/synthesis-cost-what-you-pay-per-page-and-why-03.md
project: reference-synthesis-cost
model: 
last_updated: 2026-09-07
---
## Summary

This page documents part 3 of a series on synthesis costs, explaining how [[llmwiki]]'s `synth --estimate` command prices each synthesized page. The estimator uses a formula: (per-call overhead + prompt template + body) × input_rate + completion × output_rate, with each page as an independent process and no shared cache prefix between them. PR #57 corrected four independent errors in the previous estimator and fixed the rate card (sonnet-5 corrected from $2/$10 to $3/$15 per million tokens). The current estimate achieves ±20% accuracy; real measured costs run ~10% higher.

## Key Claims

- `synth --estimate` treats each page as a completely independent API process with no shared cached prefix, making synthesis cost linear in page count
- On a mature wiki, the injected topic vocabulary in the prompt template is typically the largest fixed per-page cost, larger than agent scaffolding overhead
- The previous estimator contained four independent errors: incorrect cached prefix assumption, false cache-hit assumptions across pages, token counting at wrong ratio (4 chars/tok vs actual 2.05), and underestimated completion length (~800 vs actual ~1,372 tokens)
- The documented rate for `sonnet-5` was wrong: should be $3/$15 per million tokens, not $2/$10, derived from actual `modelUsage.costUSD` data
- `--estimate` is accurate to ±20% using a rate card and character-to-token heuristic; real measured costs were ~10% higher than estimates ($0.042 vs $0.038 per page)
- Document bodies are truncated to 8,000 characters and multi-part documents cost one API call per chunk, not one call per entire document

## Key Quotes

> "(per-call overhead + prompt template + body) x input rate + completion x output rate" — the core pricing formula

> "A large `prompt` figure means the injected topic vocabulary has grown — it is re-sent on every call, and on a mature wiki it is usually the single biggest fixed cost per page, larger than the lean scaffolding" — the dominant cost driver

> "The previous estimator was wrong in four independent ways, each verified against `--output-format json`" — systematic debugging and verification

> "`sonnet-5` was listed at $2/$10 per MTok. Derived from `modelUsage.costUSD` (905 input + 494 output = $0.010125) the real figures are **$3/$15**" — the rate card correction

> "`--estimate` never calls the API. It uses the rate card in `model_pricing.csv` plus a chars-per-token heuristic, so treat it as ±20%" — estimation methodology and caveats

## Connections

- [[llmwiki]] (project) — the synthesis system whose cost model is documented
  - fact: Each synthesized page is an independent API process with no inter-page cache sharing, making total cost scale linearly with page count.
  - fact: The prompt template (injected topic vocabulary) becomes the dominant per-page cost component on mature wikis after PR #57 corrections.

- [[Configuration Reference]] (documentation) — documents `synthesis.*` configuration keys
  - fact: `synthesis.overview_model` (defaulting to `haiku`) controls which model generates the landing-page overview, chosen for cost efficiency.

- [[prompt-caching]] (concept) — cache optimization and efficiency
  - fact: The batch API (documented in prompt-caching.md) does support shared cache prefixes; synthesis cost estimation was incorrectly modeling cache reuse that doesn't exist in independent per-page processes.