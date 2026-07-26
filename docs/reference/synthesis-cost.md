# Synthesis cost — what you pay per page, and why

`llmwiki synthesize` calls an LLM once per source page. This page explains what a call actually costs, which parts of the bill are your data and which are overhead, and how the shipped defaults were chosen.

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

**~9x cheaper, with no change to the prompt or the output contract.** On a 200-page backlog that is roughly $74 versus $8.

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

## Caveat: `synthesize --estimate` models a different call

`--estimate` predates the `claude` CLI backend and prices an Anthropic API-style call: a stable prefix (`CLAUDE.md` + `wiki/index.md` + `wiki/overview.md`) written to cache once, then re-read on every subsequent page.

The `claude` backend does not work that way. It never sends `index.md` or `overview.md`, and each invocation is a fresh process, so the prefix is largely re-written to cache every call rather than read. Treat `--estimate` as a **lower bound** for the `claude` backend. It remains accurate for `ollama` (free) and for the API-based path in [`prompt-caching.md`](prompt-caching.md).

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
- [`reference/cli.md`](cli.md) — `synthesize --check` / `--estimate`
