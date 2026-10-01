---
title: "CLI reference (part 8/19: Auto-tagging (#351))"
slug: cli-reference-08
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 8 of 19 of **CLI reference** — Auto-tagging (#351).

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate for pending sources in eligible-source units (Corpus / Already synthesized), plus `Source pages (current state): T on disk (sessions + docs + stubs)` and `Candidates (pre-run state):` (current `wiki/sources/` shape — not a forecast of the next harvest) (#50 / #90 / #81 / #113). |
| `--sources-only` | Synthesize `wiki/sources/` only — skip candidate harvest (legacy `synthesize` behaviour). Mutually exclusive with `--candidates-only` / `--check` / `--estimate`. |
| `--sessions-only` | Synthesize only `raw/sessions/` — skip `raw/docs/`. Mutually exclusive with `--docs-only`. Combinable with `--path` / `--force` (paths under `raw/docs/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--docs-only` | Synthesize only `raw/docs/` — skip `raw/sessions/`. Mutually exclusive with `--sessions-only`. Combinable with `--path` / `--force` (paths under `raw/sessions/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--path PATH` | Synthesize only this raw session or doc under `raw/sessions/` or `raw/docs/` (repeatable; relative to the vault root, or absolute under it) (#62). Exit 2 if the path is missing or outside the vault. Still honours `filters.include_subagents` / `exclude_headless` (ineligible files are skipped even when named). Incompatible with `--check` / `--estimate`. |
| `--candidates-only` | Harvest entity/concept **candidates** from already-synthesized `wiki/sources/` into `wiki/candidates/`, then exit (#90 / #147). Reads the source layer only — never `raw/` — so it runs no per-source synthesis and **no** classify LLM call; kind, description, and facts come from Connections topic bullets already on those pages. LLM cost is **zero**. Unreadable source pages still fail the run and write nothing. Mutually exclusive with `--sources-only` / `--check` / `--estimate`. |
| `--min-refs N` | Candidate threshold: a `[[wikilink]]` target becomes a candidate when **N or more distinct source pages** name it (default: `3`). |
| `--concurrency N` | Synthesize N source pages at once, overriding `synthesis.concurrency` (default: `2`; range `1`–`16`). `1` runs strictly sequentially. Pages are I/O-bound on the backend, so the wall clock shrinks roughly in proportion; raise it only as far as your provider's rate limits and your machine allow. `all` has no matching flag — its synth stage reads `synthesis.concurrency`. |
| `--backend NAME` | One-run overlay of `synthesis.backend` (`dummy` \| `ollama` \| `claude` \| `cursor_cli`). Honoured by `--check`, `--estimate`, and a real run. Does **not** write `config.json`. Unknown names exit `2`. |
| `--vault PATH` | Read/write under the vault root; configures the active `llmwiki-state.json`. |

Backend is picked from `synthesis.backend` in `config.json` / `sessions_config.json` (`dummy` by default; `ollama` for local; `claude` for synchronous `claude -p`; `cursor_cli` for Cursor Agent CLI `agent -p`, default model `composer-2.5`). Nested blocks: `synthesis.claude`, `synthesis.cursor_cli`, `synthesis.ollama` (flat `claude_*` still works). This is the **synthesis** generator — not the `cursor_cli` / `cursor_ide` session-ingest adapters. See [`configuration.md`](../configuration.md#synthesis-backend).

> **Removed in v1.4.0:** `--list-pending` and `--complete` (agent-delegate
> pending prompts). Use `synthesis.backend: claude` (or `cursor_cli`) instead.

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the deterministic baseline.  The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when `prompt-caching` is already on the page (threshold 0.80 + prefix check).

No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged.  If the backend returns no suggested-tags block (dummy backend, malformed output), the page still ships with baseline tags.

Removed: `synthesize` (use `synth`; the old name was sources-only by default) and `consolidate-topics` (known-names prepare is part of `synth`).

---
