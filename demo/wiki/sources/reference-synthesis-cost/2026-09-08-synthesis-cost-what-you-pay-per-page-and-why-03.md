---
title: "Synthesis cost — what you pay per page, and why (part 3/3: Why the default model is Sonnet, not Haiku)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, sonnet-vs-haiku, synth-estimate, model-pricing, connections-quality, wiki-synthesis, token-budget, model-selection, wikilinks]
date: 2026-09-08
source_file: 
project: reference-synthesis-cost
model: 
last_updated: 2026-09-08
---
## Summary

Part three of the synthesis-cost reference argues for keeping `claude_model: "sonnet"` as the default: Haiku is competitive on extraction (Summary / Key Claims) but weak on judgment in `## Connections`, which feeds `llmwiki graph`, backlinks, and the topic vocabulary reinjected into every later synthesis prompt. Measured runs also show Haiku 4.5’s default extended thinking bills heavily as output, erasing most of its per-token price advantage unless `MAX_THINKING_TOKENS=0`. The doc defines what `synth --estimate` prices (per-page linear cost, fixed prompt + body + completion), lists six independent fixes landed for issue #57 (wrong cache assumptions, 4 vs ~2.05 chars/token, wrong Sonnet rate card, chunking), and notes that `llmwiki build --synthesize` uses a separate cheap overview call defaulting to Haiku because it does not need graph-quality wikilinks.

## Key Claims

- Haiku and Sonnet produced effectively equivalent Summary / Key Claims on the same prompt, but Haiku linked incidental libraries, coined invalid page titles, and missed the project entity where Sonnet linked browse-worthy scopes correctly.
- Bad `## Connections` output compounds because that section alone drives the knowledge graph, backlink index, and injected topic vocabulary for subsequent syntheses.
- With default extended thinking enabled, Haiku lean synthesis cost about $0.028/page (~4,278 output tokens) versus $0.009 with `MAX_THINKING_TOKENS=0` (378 output tokens); Sonnet lean was ~$0.042 (~730 output tokens), so Haiku’s ~3× cheaper list rate only yielded ~33% savings when thinking stayed on.
- `synth --estimate` models each page as its own process with no shared cached prefix across pages: fixed overhead (agent + prompt template) plus truncated body (~8k chars) and completion, using `model_pricing.csv` and a chars-per-token heuristic (±20%; one corpus measured ~10% under real usage).
- On a mature wiki, injected topic vocabulary in the fixed prompt is often the largest per-page fixed cost, larger than lean scaffolding (~5,288 tok fixed with lean on vs ~35k with `claude_lean` off).
- Correct Sonnet pricing derived from API usage was **$3/$15** per MTok input/output, not the prior **$2/$10** `sonnet-5` row; `haiku-4.5` at $1/$5 matched measurements.
- `build --synthesize` adds one LLM overview call when the synthesis backend is `claude`, `cursor_cli`, or `ollama`; overview uses `synthesis.overview_model` (default Haiku) with the same lean flags for Claude, and is skipped for `dummy` or unavailable backends (#230).

## Key Quotes

> "Bad links compound." — Explains why Haiku’s weaker `Connections` section is a structural wiki cost, not a cosmetic formatting issue.

> "**Recommendation:** keep `claude_model: \"sonnet\"` (the default). The lean flags already removed the dominant cost, and what remains buys measurably better graph structure." — Default model guidance after lean-mode cost cuts.

> "`--estimate` never calls the API." — Clarifies that estimates are rate-card + heuristic, not live billing.

## Connections

- [[llmwiki]] (entity) — Documents per-page synthesis economics, CLI `--estimate`, and `build --synthesize` overview behavior for the wiki toolchain.
  - fact: Source-page `Connections` feed `llmwiki graph` and topic vocabulary used in later synthesis prompts.
- [[Wiki Synthesis]] (concept) — Session is entirely about backend model choice, lean flags, and estimator accuracy for the synth pipeline.
  - fact: Default production model remains Sonnet; Haiku is optional only with accepted weaker graph links and `MAX_THINKING_TOKENS=0`.
- [[Wikilinks]] (concept) — TitleCase and “significant scopes only” rules in `Connections` directly affect graph quality and downstream prompts.
  - fact: Haiku violations (lowercase-with-spaces pages, incidental libraries) degrade the link graph Sonnet avoided.
- [[Knowledge Graph]] (concept) — Only `## Connections` from source pages feeds the graph and backlink index described in the doc.
  - fact: Model choice for synthesis is partly a graph-structure trade-off, not only token price.
- [[Static Site]] (concept) — `llmwiki build --synthesize` triggers a separate landing-page overview LLM call with a cheaper default model.
  - fact: Overview defaults to Haiku because prose-from-JSON does not need source-page–quality wikilinks.
