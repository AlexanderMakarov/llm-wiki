---
title: "Synthesis cost — what you pay per page, and why (part 2/3: The lean flags)"
slug: synthesis-cost-what-you-pay-per-page-and-why-02
project: synthesis-cost-what-you-pay-per-page-and-why
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/synthesis-cost.md"
content_sha256: ed5236ca5048181277ddb59f9410748ce57939433fbfde555435273a335e5a23
---

> Part 2 of 3 of **Synthesis cost — what you pay per page, and why** — The lean flags.

## The lean flags

`ClaudeCLISynthesizer` therefore adds these to every call (see `_LEAN_ARGV` in `llmwiki/synth/claude_cli.py`):

| Flag | Removes |
|---|---|
| `--tools ""` | All built-in tool schemas |
| `--strict-mcp-config` | Every configured MCP server's tool definitions |
| `--disable-slash-commands` | The skill listing |
| `--setting-sources ""` | Settings files and `CLAUDE.md` auto-discovery |
| `--system-prompt "<short>"` | The full agent system prompt |

`--tools` is variadic, so its empty-string value must be followed by another `--flag` — the argv order in `_LEAN_ARGV` is load-bearing, and `test_lean_tools_flag_is_followed_by_a_flag` pins it.

Measured end-to-end on one real page, same prompt, same model:

| Configuration | Input | Output | **$/page** |
|---|---|---|---|
| `sonnet`, no lean flags | 58,169 | 1,299 | **$0.369** |
| `sonnet`, lean flags | 4,607 | 730 | **$0.042** |

**~9x cheaper, with no change to the prompt or the output contract.**

That single page was a small, clean demo session. Across **29 real vault pages** the same lean configuration measured:

| | mean | spread |
|---|---|---|
| Input tokens | 9,282 | 6,251 – 10,254 |
| Output tokens | 1,372 | 902 – 2,554 |
| **Cost** | **$0.0763/page** | |

Real transcripts are roughly twice the size of the demo and generate about twice the page, so budget **~$0.08/page**, not $0.04. On a 200-page backlog that is roughly $74 without the lean flags versus **$15** with them.

### Where the prompt sits decides what you pay for it

Input is billed as a 1-hour cache **write** at 2x the fresh rate, not at the plain input rate. What varies is whether you ever get the **read** back at 0.1x.

Originally every page sent the whole prompt as one user message. Measured across 29 pages, `cache_read_input_tokens` was **0** on all of them: the CLI places a single cache breakpoint at the end of the user message, so the key covers the body too and no two pages ever share one. The template and vocabulary — byte-identical across the run — were re-written at 2x on every page.

The fix is placement, not size. The template splits at `## Session to synthesize` into a run-stable half and a per-page half; the stable half goes into the **system prompt**, which the CLI *does* reuse across invocations:

| | page 1 (cold) | page 2+ |
|---|---|---|
| cache write | 9,715 | ~5,000 |
| **cache read** | 0 | **4,642** |
| $/page | $0.092 | **~$0.057** |

About **25% off steady-state**, on top of the lean flags. The remaining write is the page body, which is genuinely unique and cannot be cached.

### Other backends and other providers

The split is **not** Claude-specific. `split_prompt_template()` lives in `llmwiki/synth/base.py`, the shared backend contract, and returns `(stable_prefix, per_page_tail)`. Every provider bills a repeated prefix more cheaply than fresh input; they just want it in different places, so each backend maps the stable half onto its own mechanism:

| Backend | Where the stable half goes | Mechanism |
|---|---|---|
| `claude` CLI | `--system-prompt` | 1h prompt cache, reused across invocations |
| `ollama` | `system` field on `/api/generate` | KV-cache prefix reuse (no billing) |
| OpenAI / OpenRouter *(not built)* | leading system message | automatic prefix caching, ~50% off repeated prefixes |
| Anthropic API *(scaffolded)* | `cache_control` breakpoint after the prefix | explicit, see [`prompt-caching.md`](prompt-caching.md) |

A new backend gets the benefit by calling `split_prompt_template()` and putting the prefix wherever its provider caches. A template with no marker — a user's custom prompt — returns an empty prefix and the whole template as the tail, so it still synthesizes correctly; caching is an optimisation, never a correctness requirement.

Two caveats for a hypothetical OpenAI/OpenRouter backend. Its prefix caching is automatic but needs the prefix to be **identical and leading**, so the stable half must come first in the messages array — the same discipline, unenforced. And OpenRouter's discount depends on which upstream provider serves the request, so the same model can bill differently run to run; `model_pricing.csv` assumes one rate per model and would need a per-provider row.

### Vocabulary size is now nearly free

Because the vocabulary rides in the cached prefix, it is written once per run and read at 0.1x thereafter — so breadth costs almost nothing. `_VOCAB_LIMIT` was raised **80 → 200** on that basis. A topic missing from the list gets re-coined under a new spelling, which fragments the graph and the backlink index; that is the failure the list exists to prevent, and it was previously being traded away to save tokens that caching now makes cheap.

### Turning it off

Lean mode is on by default. Opt out only if you deliberately want the model to see your `CLAUDE.md` or use tools during synthesis:

```jsonc
{ "synthesis": { "backend": "claude", "claude_lean": false } }
```

Only an explicit `false` opts out; a missing or malformed value keeps the default on.

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
