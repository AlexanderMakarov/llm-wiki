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

The rate card llmwiki prices against lives in [`model_pricing.csv`](../../model_pricing.csv) at the repo root — one row per model, with `aliases` mapping CLI names (`sonnet`, `claude-haiku-4-5-20251001`) onto pricing rows. Update that file when provider pricing changes; nothing else hardcodes rates.

## Where the money actually goes

The synthesis prompt — format rules, topic vocabulary, and a session body capped at 8 KB — is about **2,100 tokens**. But by default the `claude` CLI wraps every call in a full coding-agent context: its system prompt, all built-in tool schemas, every configured MCP server's tools, auto-discovered `CLAUDE.md` files, and the skill listing.

None of that is reachable by a synthesis call. The backend passes a prompt on stdin and reads stdout; it never lets the model use a tool. Measured with a trivial one-line prompt, in a repo with several MCP servers configured:

| Configuration | Input tokens |
|---|---|
| `claude -p -` (bare) | **35,081** |
| `claude -p -` + lean flags | **700** |

So on a default setup, **~95% of the input bill is scaffolding the task cannot use.**

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
