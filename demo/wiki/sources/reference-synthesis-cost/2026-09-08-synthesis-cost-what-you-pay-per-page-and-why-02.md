---
title: "Synthesis cost — what you pay per page, and why (part 2/3: The lean flags)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-synthesis-cost, prompt-caching, lean-synthesis, token-budget, multi-backend-synthesis, lean-argv, claude-cli-synth]
date: 2026-09-08
source_file: 
project: reference-synthesis-cost
model: 
last_updated: 2026-09-08
---
## Summary

Part 2 documents how `ClaudeCLISynthesizer` uses `_LEAN_ARGV` to strip tool schemas, MCP definitions, slash commands, settings/`CLAUDE.md` discovery, and the full agent system prompt from each synthesis call, cutting measured cost on one demo page from about **$0.37 to $0.04** (~9×) with the same prompt and output contract. On **29 real vault pages**, lean mode averages **~$0.08/page**; a **200-page backlog** is roughly **$74 vs $15** with lean. A second win comes from **where** the prompt lives: moving the run-stable template (split at `## Session to synthesize`) into **`--system-prompt`** so the CLI reuses a 1-hour cache breakpoint yields **cache reads on page 2+** and steady-state **~$0.057/page** (~25% below lean-only). `split_prompt_template()` in `llmwiki/synth/base.py` is shared so **cursor_cli**, **Ollama**, and future OpenAI/OpenRouter/Anthropic backends can place the stable prefix where each provider caches; vocabulary in the cached prefix justified raising **`_VOCAB_LIMIT` from 80 to 200**. Lean mode defaults on; only explicit `synthesis.claude_lean: false` opts out.

## Key Claims

- Empty `--tools ""` in `_LEAN_ARGV` must be immediately followed by another `--flag` because `--tools` is variadic; argv order is load-bearing and covered by `test_lean_tools_flag_is_followed_by_a_flag`.
- With the full prompt in a single user message, measured `cache_read_input_tokens` was **0 on all 29 pages** because the CLI’s cache breakpoint at the end of the user message prevents sharing byte-identical template/vocabulary across pages (each page re-paid cache **write** at 2×).
- After splitting stable vs per-page content, page 1 cold cost was ~**$0.092/page**; page 2+ showed ~**4,642** cache read tokens and ~**$0.057/page** steady state.
- Real vault synthesis with lean flags: mean **9,282** input tokens (spread 6,251–10,254), mean **1,372** output tokens (902–2,554), mean cost **$0.0763/page**.
- A custom prompt with no `## Session to synthesize` marker returns an empty stable prefix and the full template as the tail—synthesis stays correct; prefix caching is an optimization only.
- OpenRouter prefix-cache discounts can vary by upstream provider; `model_pricing.csv` assumes one rate per model and would need per-provider rows for accurate OpenRouter costing.

## Key Quotes

> "~9x cheaper, with no change to the prompt or the output contract." — headline result of lean flags on one measured demo page (sonnet, same prompt).

> "The fix is placement, not size." — cache savings come from putting the run-stable half in a reused system prompt, not from shrinking the template.

> "caching is an optimisation, never a correctness requirement." — `split_prompt_template()` behavior when no split marker exists.

## Connections

- [[llmwiki]] (entity) — documents synthesis cost controls (`_LEAN_ARGV`, `split_prompt_template()`, `claude_lean` config) in the reference synthesis-cost series.
  - fact: Lean synthesis defaults on; opt-out is `synthesis.claude_lean: false` only.
- [[Wiki Synthesis]] (concept) — automated pass that calls provider backends; this page explains per-page token and dollar drivers for the Claude CLI path.
  - fact: Budget **~$0.08/page** on real transcripts with lean flags, not the ~$0.04 single demo page.
- [[Cursor]] (entity) — `cursor_cli` backend prepends the stable prompt half on stdin and uses a truncated tool allowlist; no equivalent lean strip of the full agent system prompt.
- [[Ollama]] (entity) — maps stable prefix to the `system` field on `/api/generate` for KV-cache reuse (no billing).
- [[Adapters]] (concept) — new synthesis backends are expected to call `split_prompt_template()` and attach the stable prefix to each provider’s caching mechanism.
- [[MCP Server]] (entity) — `--strict-mcp-config` in lean mode removes configured MCP server tool definitions from synthesis calls (distinct from wiki’s own MCP tools for search/read).
