---
title: "CLI reference (part 5/8: synth — synthesize sources + harvest candidates)"
slug: cli-reference-05
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 5 of 8 of **CLI reference** — synth — synthesize sources + harvest candidates.

## `synth` — synthesize sources + harvest candidates

Primary command (#90). Default runs **both** lists: pending sources → `wiki/sources/`, then entity/concept candidates → `wiki/candidates/`.

```bash
python3 -m llmwiki synth --check            # probe the backend
python3 -m llmwiki synth --estimate         # cost + Candidates (pre-run state)
python3 -m llmwiki synth --force            # re-synth everything, then harvest
python3 -m llmwiki synth --sources-only     # legacy: sources only
python3 -m llmwiki synth --sessions-only    # all pending sessions (skip docs)
python3 -m llmwiki synth --docs-only        # all pending docs (skip sessions)
python3 -m llmwiki synth --candidates-only   # entity/concept candidates only
python3 -m llmwiki synth --candidates-only --min-refs 5
python3 -m llmwiki synth --path raw/sessions/<file>.md
python3 -m llmwiki synth                    # real run (sources + candidates)
```

`llmwiki synthesize` is a **deprecated** alias: it warns and defaults to `--sources-only` so existing scripts do not suddenly write candidate stubs. Prefer `synth`.

Before the first page is synthesized, a real run announces the batch: `Synthesizing 11 source(s) with ClaudeCLISynthesizer (2 at a time)` — the count is the work queue after up-to-date, ineligible, and already-claimed sources are excluded, so it is what the run will actually do. An empty queue says `Nothing to synthesize — every source is already up to date.` instead. Each result line then carries its position, `  [3/11] synthesized: <project> → <page>`, counting completed **sources** against that total; pages finish in whatever order the backend returns them, so the positions arrive out of order while the last one is always `N/N`.

`--estimate` prints the sources cost estimate with honest input units (#81): **Corpus: N eligible sources (S sessions + D docs)** and **Already synthesized: N of M eligible sources** (not page/file counts under `wiki/sources/`), then a separate **Source pages (current state): T on disk (Sess sessions + D docs + X stubs)** line for on-disk `.md` file counts. It also prints a `Candidates (pre-run state):` block — the harvestable shape of `wiki/sources/` **as it exists now**, with a note that pending sources are not yet reflected. It is not a forecast of what the next run will harvest (#113). After a successful real `synth` (not estimate), the CLI prints an end-of-run summary: `Synthesized:`, `Duration:`, optional `Tokens:` / `Cost:` when known. Harvest still prints its Candidates line once; the end summary does not repeat Candidates.

### Flags

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate for pending sources in eligible-source units (Corpus / Already synthesized), plus `Source pages (current state): T on disk (sessions + docs + stubs)` and `Candidates (pre-run state):` (current `wiki/sources/` shape — not a forecast of the next harvest) (#50 / #90 / #81 / #113). |
| `--sources-only` | Synthesize `wiki/sources/` only — skip candidate harvest (legacy `synthesize` behaviour). Mutually exclusive with `--candidates-only` / `--check` / `--estimate`. |
| `--sessions-only` | Synthesize only `raw/sessions/` — skip `raw/docs/`. Mutually exclusive with `--docs-only`. Combinable with `--path` / `--force` (paths under `raw/docs/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--docs-only` | Synthesize only `raw/docs/` — skip `raw/sessions/`. Mutually exclusive with `--sessions-only`. Combinable with `--path` / `--force` (paths under `raw/sessions/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--path PATH` | Synthesize only this raw session or doc under `raw/sessions/` or `raw/docs/` (repeatable; relative to the vault root, or absolute under it) (#62). Exit 2 if the path is missing or outside the vault. Still honours `filters.include_subagents` / `exclude_headless` (ineligible files are skipped even when named). Incompatible with `--check` / `--estimate`. |
| `--candidates-only` | Harvest entity/concept **candidates** from already-synthesized `wiki/sources/` into `wiki/candidates/`, then exit (#90). Reads the source layer only — never `raw/` — so it runs no per-source synthesis; cost is at most **one batched call** to classify the harvested names as entity vs concept, regardless of corpus size. Classification is fail-closed: any new target left unclassified stops the run with a non-zero exit and **writes nothing**, naming the cause (unreachable backend, incomplete/unparseable reply after retry, or unreadable source pages). Mutually exclusive with `--sources-only` / `--check` / `--estimate`. |
| `--min-refs N` | Candidate threshold: a `[[wikilink]]` target becomes a candidate when **N or more distinct source pages** name it (default: `3`). |
| `--concurrency N` | Synthesize N source pages at once, overriding `synthesis.concurrency` (default: `2`; range `1`–`16`). `1` runs strictly sequentially. Pages are I/O-bound on the backend, so the wall clock shrinks roughly in proportion; raise it only as far as your provider's rate limits and your machine allow. `all --with-synth` has no matching flag — it reads `synthesis.concurrency`. |
| `--vault PATH` | Read/write under the vault root; configures the active `llmwiki-state.json`. |

Backend is picked from `synthesis.backend` in `config.json` / `sessions_config.json` (`dummy` by default, `ollama` for local, `claude` for synchronous `claude -p`). See [`configuration.md`](../configuration.md#synthesis-backend).

> **Removed in v1.4.0:** `--list-pending` and `--complete` (agent-delegate
> pending prompts). Use `synthesis.backend: claude` instead.

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the deterministic baseline.  The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when `prompt-caching` is already on the page (threshold 0.80 + prefix check).

No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged.  If the backend returns no suggested-tags block (dummy backend, malformed output), the page still ships with baseline tags.

---
