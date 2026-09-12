# Search command and findability checks (#197)

Maintainer rationale for `llmwiki search`, the three findability lint rules, and the demo acceptance gate. User-facing behaviour lives in [`docs/reference/cli.md`](../reference/cli.md); numbers in [`docs/benchmarks.md`](../benchmarks.md).

## Why a real `search` command (and not `eval`)

[`DECLINED.md`](DECLINED.md) (2026-08-26 — Eval framework / `llmwiki eval`) declines a scoring CLI **unless it is a real subcommand with tests**. The old `eval` story was docs advertising a shipped tool while CI ran a no-op behind `|| true`.

#197 takes that escape clause deliberately:

- Ship **`llmwiki search`** — a real, tested, read-only subcommand that exposes the same literal engine as MCP `wiki_search`.
- Do **not** revive `llmwiki eval`.
- Gate quality with **pytest + lint** (`page_findability`, `title_ambiguity`, `search_consistency`, plus `tests/test_197_acceptance.py` against committed fixtures), not a separate scoring CLI.

## Why P@k / R@k / F1 / nDCG were rejected

Issue #197 asked for precision/recall/F1/nDCG. Against this ground truth those metrics are degenerate:

- Every derived lookup has **exactly one** correct answer (a page title names one page; a wikilink anchor resolves to one target).
- Precision and recall at cutoff *k* both collapse to “is the answer at rank ≤ *k*”.
- F1 restates that same binary fact.
- nDCG reduces to `1/log2(rank+1)` for a single relevant document.

Reporting all four would state one fact four times. The gate instead records **found-rate** (invariant: every titled page returned), **rank-1 rate**, and **MRR** (cutoff-free, carries the full rank distribution). Cutoffs used in product surfaces remain top-1 and top-5 (agent default).

## Wikilink lookups and present terms

`page_findability` also samples resolved `[[wikilink]]` anchors (alias map + resolver shared with the graph). Bare names use match mode (path/title/body); multi-word anchors use extract/`rank_of`. Failures name the link text and expected target; an info line states how many lookups were checked. Cold `wiki/archive/` pages never enter the answer key (same exclusion as search).

`search_consistency` present terms come only from **scanned** raw pages (first/last by `rel_path`), never from oversize or budget-skipped files.

## Survival share is information

`search_consistency` and the acceptance test report how many planted session terms also appear in wiki text. Synthesis routinely drops wording; a low share is normal. Planted demo terms sit in `raw/sessions/` until those sessions are re-synthesized — wiki survival can be 0% without any search bug. Never fail CI on that share.
