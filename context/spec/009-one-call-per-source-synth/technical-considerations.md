# Technical Specification: One synthesis pass per source

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (approved, FR5 amended 2026-08-16) — GitHub Issues [#147](https://github.com/AlexanderMakarov/llm-wiki/issues/147) and [#145](https://github.com/AlexanderMakarov/llm-wiki/issues/145)
- **Status:** Completed
- **Author(s):** AWOS `/implement-feature` (agent)

---

## 1. High-Level Technical Approach

Karpathy’s ingest is one integration of a raw file: write a summary, and maintain the entity/concept pages that file touches. This repo had split that into **four** later LLM jobs. This change collapses them to **two jobs per `synth` run**, then bookkeeping.

| Order | LLM job | Replaces | When |
| --- | --- | --- | --- |
| **1** | **Prepare the known-names list** from wiki already on disk (canonical spelling, aliases, kind, short description) | Harvest classifier + `consolidate-topics` + the “what is this name” half of `key_facts.md` | **Once, at the start of the run**, before any new source |
| **2** | **Source summary** for each new (or rewrite-queued) raw file, with that frozen list in the cached prompt prefix | `source_page.md`, plus this source’s facts (authored while the transcript is in context — #103 / #147) | Once per queued source |

Harvest and promote are parsers and a file move. They do not call the model. `## Connections` on a **candidate / entity / concept** page remains the evidence / related-links list. The source page still **names** topics (today under `## Connections` on the source); those name-lines gain parseable kind / description / facts. Key Claims / Key Quotes are unchanged in this work.

A Ctrl+C then a new `synth` runs job 1 again, so the second run’s list includes names from pages the first run wrote. Job 1 is never repeated mid-run.

**Honest accounting:** one amortised LLM ask per run (job 1) + one ask per queued source (job 2). Dummy / non-LLM backends skip job 1 and inject the heuristic graph vocabulary already used today, so tests stay offline.

No new runtime dependencies. Parallelism (#118) is unchanged. No Python CLI specialist is hired; this spec was drafted after code-explorer. QA slice uses `testing-expert`.

**Systems affected:** `llmwiki/synth/pipeline.py`, `llmwiki/synth/prompts/source_page.md`, `llmwiki/topics_consolidate.py` / `llmwiki/topics.py`, new `llmwiki/source_topics.py`, `llmwiki/candidates_harvest.py`, `llmwiki/candidates.py`, `llmwiki/cli.py`, `llmwiki/build.py` / `llmwiki/state_store.py`, docs / CHANGELOG / agent kit / UPGRADING.

---

## 2. Proposed Solution & Implementation Plan

### 2.1 Job 1 — prepare known-names (once per run)

Call a new `prepare_known_names(wiki_dir, backend) -> vocab_text` from `synthesize_new_sessions` **after** the queue is known to be non-empty (or whenever there are existing topics even if the queue is empty — only needed when job 2 will run). Inject the result through the existing `_inject_vocabulary` / `{vocabulary}` slot so the prefix stays **byte-identical for every page of the run** (`split_prompt_template` at `## Session to synthesize`, `_VOCAB_LIMIT = 200`).

**Input:** topic graph already on disk (`build_topic_graph`) plus opening paragraphs / kinds from `wiki/entities/`, `wiki/concepts/`, `wiki/candidates/**`. Do **not** re-read `raw/`.

**Output (structured, parsed):** canonical `name`, `aliases`, `kind` (`entity` | `concept`), one-line `description`. Persist via the existing `.llmwiki-topics.json` shape (`topics_consolidate.parse_and_cache`) so `desc=` and aliases keep working — **written by synth**, never by a user-facing consolidate command.

**When to skip job 1:** Dummy / `not is_llm` backend; no topics on disk yet; `--dry-run` / `--estimate` / `--check`. Fall back to today’s heuristic `_inject_vocabulary` (graph, no LLM). If the real backend throws, warn and use the same heuristic rather than aborting the run.

**Prompt:** adapt `llmwiki/synth/prompts/topic_consolidation.md` to also emit `kind` per canonical topic. Keep one call per run (chunk only if the candidate list would overflow a single reply — same `DEFAULT_CLASSIFY_BATCH` spirit, still “the known-names job”, not per-source). Job 1 does **not** rewrite `## Key Facts` on topic pages and does **not** re-read transcripts.

### 2.2 Job 2 — source page contract

Extend `source_page.md` so each named topic in the source’s topic list (the existing `## Connections` bullets harvest already counts) carries:

```markdown
- [[ExactName]] (entity) — one-line description
  - fact: A concrete claim this source supports.
```

`kind` is `entity` or `concept`. Prefer the exact `name` from the known-names list. New names may appear; they get kind / description / facts here. Do not add a sibling `## Topics` outline and do not remove Key Claims / Key Quotes in this change.

**Parser** — `llmwiki/source_topics.py`:

| Function | Role |
| --- | --- |
| `parse_source_topics(body) -> list[TopicRecord]` | `name`, `kind`, `description`, `facts: list[str]` from those bullets |
| `source_page_needs_topics_rewrite(body) -> bool` | True when the page has `[[wikilinks]]` in Connections (or anywhere harvest would count) but no parseable kind on those names |

Malformed kind → `kind=None`; harvest defaults a **new** stub to `entity`, never an LLM guess.

Vault `wiki/prompts/source_page.md` still wins; UPGRADING says an old override without this bullet shape stays in the rewrite queue.

### 2.3 Queue rewrite (FR2)

In `synthesize_new_sessions` skip logic (~1516–1541): if the existing page for this source (or the page that already claims `source_key`) `source_page_needs_topics_rewrite`, **do not skip** — synthesize into that same path (`_build_source_page` tag preservation unchanged). After the new shape is present and raw mtime is current, skip as today. `--force` and stub pages unchanged. Withheld placeholders do not count as migrated.

### 2.4 Harvest — no classifier

`run_harvest` / `write_stubs`:

- Names / `min_refs`: keep `wikilink_targets` over `wiki/sources/`.
- Kind: `parse_source_topics` across citing sources; majority `entity` vs `concept`; tie → first sorted slug; existing stub folder still wins.
- Key Facts: concatenate that name’s `fact` lines, each suffixed `[[source-slug]]`. Empty if none.
- Description: first non-empty source-bullet description in sorted slug order, as the paragraph between `# Name` and `## Key Facts`. Re-harvest does not overwrite existing prose above `## Connections` (`_preserved_body`).
- **Candidate `## Connections`:** still the evidence list of source slugs (unchanged heading, different content from the source page).
- `classify_names` unused on the default path. `backend=` may remain on the signature and is ignored for classification. Harvest succeeds with `backend=None` and Dummy. Remove fail-closed “backend unreachable → refuse harvest”.

### 2.5 Promote — move

`promote` / flip-promote / site API: rewrite `status` / `type` as today; if Key Facts empty, fill from `parse_source_topics` on `sources:` pages; if still empty, leave empty. **Never** `synthesize_key_facts`, **never** `KeyFactsBackendError`, **never** clip a sentence near `[[Name]]`. Keep `rewrite_key_facts` as an opt-in CLI that still needs a backend — not part of review.

### 2.6 Interrupt + honest counts (#145)

`synthesize_new_sessions` on `KeyboardInterrupt` (after in-flight drain):

- `_record_abandoned_pages` records a source **only** when `error is None`, `written` is non-empty, and those files exist (fixes done-count > page-count).
- `refresh_synth_pending`; gated index rebuild if anything was written.
- Return `summary["interrupted"] = True` instead of re-raising.

`cmd_synthesize`: if interrupted, run `run_harvest` unless `--sources-only` (print `llmwiki synth --candidates-only` in that case); then exit **130**.

`build._ensure_synth_pipeline_snapshot`: also refresh when `pipeline_on_disk_mismatch` — stored row `on_disk` totals disagree with `len(list(wiki/sources/**/*.md))`. Matching snapshots skip.

### 2.7 Retire `consolidate-topics` CLI

Keep the subparser so the name resolves. Help and body: synthesis now prepares names; the command is gone; exit 2. `--complete` does not write the cache. `tests/e2e/test_cli_smoke.py` asserts that message. README / `docs/reference/cli.md` / UPGRADING / agent kit (`wiki-synth`, `wiki-candidates`) drop the prompt/`--complete` dance. `topics_consolidate.py` stays as the library job 1 uses. Do not edit `demo/raw/` (immutable).

### 2.8 Files

| Path | Responsibility |
| --- | --- |
| `llmwiki/source_topics.py` | Parse source topic bullets; rewrite detector |
| `llmwiki/synth/prompts/source_page.md` | Job 2 bullet contract |
| `llmwiki/synth/prompts/topic_consolidation.md` | Job 1: also emit `kind` |
| `llmwiki/synth/pipeline.py` | Job 1 once; FR2 queue; interrupt return; abandoned-page disk check |
| `llmwiki/topics_consolidate.py` / `topics.py` | Job 1 parse/cache; `_inject_vocabulary` consumes it |
| `llmwiki/candidates_harvest.py` | Kind/facts/description from parser; no classifier |
| `llmwiki/candidates.py` | Promote without LLM |
| `llmwiki/cli.py` | Interrupt harvest + 130; retire consolidate-topics |
| `llmwiki/build.py` + `state_store.py` | `on_disk` mismatch |
| docs / CHANGELOG / agent kit / UPGRADING | FR10 |

---

## 3. Impact and Risk Analysis

### System Dependencies

- **#118:** job 2 still one `synthesize_source_page` per source/chunk; vocab prefix unchanged within a run. Job 1 runs on the main thread before the executor.
- **#103:** promote must not grow a clip-from-mention path.
- **#108:** topic pages already render prose above Connections; harvest’s opening paragraph + Key Facts show with no UI change.
- **#102:** kinds remain `entity` \| `concept` only.
- **Site candidates API:** same `promote()`; `KeyFactsBackendError` is not a promote failure.

### Potential Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Job 1 fails or Dummy has no LLM | Heuristic `_inject_vocabulary`; run continues |
| Model omits kind on source bullets | Rewrite detector re-queues; harvest defaults new stubs to entity |
| Vault prompt override lacks the new bullets | UPGRADING; rewrite queue keeps firing |
| Catch-up rewrite of a large vault | One job-2 call per old source, once; Ctrl+C + restart re-runs job 1 |
| Job 1 invalidates the cached prefix | It runs **before** the executor; prefix is stable for all job-2 pages |
| Interrupt tests expect `KeyboardInterrupt` | Switch to `summary["interrupted"]` + CLI 130 |
| Stale Home refresh every build | Refresh only on integer mismatch |

---

## 4. Testing Strategy

All tests: `DummySynthesizer` / `tmp_path` — no live model, no live vault. Spy that harvest/promote do not call `synthesize_source_page` / `synthesize_key_facts`.

| Area | Lock |
| --- | --- |
| `tests/test_source_topics.py` | Parse bullets; rewrite detector |
| Job 1 | Called once per real-LLM run before workers; Dummy skips it; vocab identical across pages of a run |
| Harvest | Kind/facts/description from bullets; Dummy/None backend; classifier unused |
| Promote | Dummy/None succeeds; edited Key Facts preserved; mention-clip not used |
| FR2 | Old Connections-only page queued despite current mtime; new-shape page skipped |
| Interrupt | `interrupted` flag; harvest ran; unfinished rel absent from state; written files recorded only if they exist |
| Build | `on_disk: 0` + files on disk → refresh; matching counts → skip |
| CLI | `consolidate-topics` exit 2; `--help` does not teach `--complete` as a lifecycle step |

Acceptance mapping: FR1 job 2 + parser; FR2 rewrite detector; FR3 harvest offline; FR4 promote offline; FR5 job 1 once + restart; FR6 interrupt harvest + build mismatch; FR7 retired command; FR8 description paragraph, no fact-count rewriter; FR9 start line + interrupt messaging; FR10 docs.
