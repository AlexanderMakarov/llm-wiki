---
title: "CLI reference (part 7/19: synth — synthesize sources + harvest candidates)"
slug: cli-reference-07
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 7 of 19 of **CLI reference** — synth — synthesize sources + harvest candidates.

## `synth` — synthesize sources + harvest candidates

Primary command (#90 / #147). Default runs **both** phases: pending sources → `wiki/sources/`, then entity/concept candidates → `wiki/candidates/`.

A real sources pass is **two language-model jobs**, then bookkeeping: (1) prepare known-names once at the start of the run (canonical name, aliases, kind, short description) from wiki already on disk — Dummy / `not is_llm` skips this and uses heuristic vocabulary inject; because that one call can take a minute or more, it first prints `Preparing known names from N candidate topic(s) (~S KB prompt) — one language-model call, may take a minute…` (no line when it is skipped or there are no candidates); (2) **one** source-summary ask per queued raw file, with that frozen list in the prompt (vocabulary may include `kind="entity|concept"` when known — #257). Connections bullets name each topic with kind and nested `fact:` claims.

Job 1 is **known-names preparation** (builds the vocabulary the source-summary prompts see, including kind). The later offline **candidates harvest** (after sources, or `synth --candidates-only`) only parses those Connections bullets into `wiki/candidates/` — **no** classify LLM call; harvest cost alone is **zero** LLM. Do not treat them as one stage. Pages that only lack usable `(entity)` / `(concept)` labels on Connections — and whose targets already have matching wiki filings — should use `llmwiki migrate topic-kinds` for label-only catch-up (#174), not a full paid re-synth.

**Clean stop (#145 / #181).** Ctrl+C, or a backend usage limit (the synthesizer's error message says the account's session or usage quota is exhausted), stops the run from starting new sources. Queued sources are cancelled; pages already in flight finish and are recorded (page, state entry, pending removal). The run then does the same bookkeeping as a successful one — a single `wiki/log.md` entry marked `stopped early` with a `Deferred:` count, pending refresh, index rebuild — and harvests candidates from what was written (unless `--sources-only`, which prints `llmwiki synth --candidates-only`). A usage-limit stop prints one line, `Stopped after N/M source(s) — backend usage limit (resets <time>); waiting for K page(s) already in flight.`, instead of an error per remaining source. Sources that did not run are **deferred**, not errors: they stay pending and the next run picks them up. All three backends (Claude CLI, Cursor Agent CLI, Ollama) recognise a usage limit from the message text (`hit your … limit`, `usage limit`, `quota exceeded`, …); a plain rate-limit `429` / "Too Many Requests" is a per-source error. If the limit hits the known-names preparation, no page is sent and every queued source is deferred. Pressing Ctrl+C a second time while in-flight pages finish kills the Claude / Cursor CLI processes and ends the run; those pages stay pending. Ollama has no child process, so a second Ctrl+C there waits for in-flight requests up to the Ollama timeout. `synth` never rebuilds `site/` — after a successful run or a stop, run `llmwiki build`.

Exit codes:

- `0` — every queued source was synthesized (and harvested, unless `--sources-only`).
- `1` — at least one source failed, or harvest failed.
- `2` — usage error (bad flags or paths).
- `75` — stopped on the backend's usage limit; retry after the reset time.
- `130` — interrupted with Ctrl+C.

A stop exits `75` / `130` even when some sources in the same run also failed; those errors are still printed.

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

`llmwiki synth` is the synthesize entry. Known-names prepare runs at the start of each sources pass.

Before the first page is synthesized, a real run announces the batch: `Synthesizing 11 source(s) with ClaudeCLISynthesizer (2 at a time)` — the count is the work queue after up-to-date, ineligible, and already-claimed sources are excluded, so it is what the run will actually do. An empty queue says `Nothing to synthesize — every source is already up to date.` instead. Each result line then carries its position, `  [3/11] synthesized: <project> → <page>`, counting completed **sources** against that total; pages finish in whatever order the backend returns them, so the positions arrive out of order while the last one is always `N/N`.

`--estimate` prints the sources cost estimate with honest input units (#81): **Corpus: N eligible sources (S sessions + D docs)** and **Already synthesized: N of M eligible sources** (not page/file counts under `wiki/sources/`), then a separate **Source pages (current state): T on disk (Sess sessions + D docs + X stubs)** line for on-disk `.md` file counts. It also prints a `Candidates (pre-run state):` block — the harvestable shape of `wiki/sources/` **as it exists now**, with a note that pending sources are not yet reflected. It is not a forecast of what the next run will harvest (#113). After a successful real `synth` (not estimate), the CLI prints an end-of-run summary: `Synthesized:`, `Duration:`, optional `Tokens:` / `Cost:` when known. Harvest still prints its Candidates line once; the end summary does not repeat Candidates.

**`--estimate` writes vault state.** It calls no backend and touches no page, but it records its result in the vault's `llmwiki-state.json`: the pending list (`synth.pending`), the Home Pipeline rows (`synth.pipeline`) and the estimate block (`synth.estimate`) — what the Home page's Pipeline counts show. Pending is judged by file modification times, so right after a `git clone`, `checkout` or `pull` every source looks changed and the estimate records them all as pending. In a vault whose state file is committed (such as the repository's `demo/`), discard that change instead of committing it.

### Flags
