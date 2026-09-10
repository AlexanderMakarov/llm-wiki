# Technical Specification: Search Command and Findability Checks

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) — issue [#197](https://github.com/AlexanderMakarov/llm-wiki/issues/197)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Search logic today is fused into the MCP server: `_wiki_search_match` and `_wiki_search_extract` each interleave three unrelated concerns in one loop — walking and reading the corpus, scoring one page against one query, and assembling and rendering results. That fusion is why a lookup costs a full corpus read, and why any batch evaluator would have to reimplement scoring and drift from it.

The change extracts those three concerns into a new root-agnostic `llmwiki/search/` package, and makes the engine **multi-query in a single pass**: it visits each page once and evaluates every pending query against it, each query carrying its own cap accumulators. A one-query search is simply the N=1 case, so there is one implementation and drift is impossible by construction rather than prevented by a test.

Single-pass matters beyond elegance. Calling a single-query engine N times over a materialised corpus would hold the whole corpus in memory — 2.4 MB of wiki text doubles once lowercased, and `include_raw` on a large vault turns 26.7 MB into ~53 MB. A streaming multi-query pass holds only per-query result state.

Everything else consumes that package:

| Consumer | What it does |
|---|---|
| `llmwiki/mcp/server.py` | Same tool contract, output byte-identical; the two handlers become scan → engine → render |
| `llmwiki search` (new CLI) | Scan → engine → render, honouring `--vault` |
| Three lint rules | Share one scan per lint run; derive their own answer key |
| `tests/test_197_acceptance.py` | Reads prepared fixtures, asserts exactly, writes nothing |

No new runtime dependency. Stdlib plus `markdown`, as the architecture requires.

**On `DECLINED.md:224`.** That entry declines an `llmwiki eval` subcommand *"unless it is a real subcommand with tests"*. This adds `llmwiki search` — a real command with tests — and no `eval` command. The scoring that #154 withdrew was a CI no-op behind `|| true` that reported success while measuring nothing; §4 here requires the opposite, and the decision is recorded in maintainer docs rather than user-facing pages.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 New package: `llmwiki/search/`

Root-agnostic by rule: every entry point takes explicit paths and the package holds **no import-time state**. This is what confines `mcp/server.py`'s import-time `CONTENT_ROOT` binding to the MCP layer and makes `--vault` targeting work everywhere else.

| File | Responsibility |
|---|---|
| `corpus.py` | `ScannedPage`, `CorpusScan`, `scan_corpus()` — the walk, the byte caps, cold-storage exclusion, frontmatter parse |
| `scoring.py` | `ExtractQuery`, `score_extract()`, `match_page()` — pure per-page functions, no I/O |
| `engine.py` | `search_extract()`, `search_match()` — multi-query, single pass over an iterable of pages; owns per-query result caps and ordering |
| `evaluate.py` | Answer-key derivation, deterministic sampling, metric computation |
| `__init__.py` | Public surface |

**Key contracts** (shapes, not implementations):

- `ScannedPage` — `rel_path: str` (relative to content root), `path: Path`, `text: str`, `text_lower: str`, `title: str`, `meta: dict`, `size: int`, `is_raw: bool`. `text_lower` is precomputed once because both modes lowercase every page on every call today.
- `CorpusScan` — `pages: list[ScannedPage]`, `budget_exhausted: bool`, `skipped_oversize: int`. The two completeness flags the MCP contract already reports.
- `scan_corpus(roots, *, content_root, cold_storage_root, per_file_cap, aggregate_budget) -> CorpusScan` — lifted from `_iter_scan_files` + `_read_capped`, behaviour unchanged. Caps stay at their current values (4 MiB/file, 50 MiB/call, `#483`).
- `ExtractQuery.parse(question)` — holds `raw`, `lower`, `tokens`. Tokenisation moves out of the per-page loop: it currently runs once per page, and must run once per **query**.
- `score_extract(page, query) -> float` — the existing arithmetic verbatim: body +50 phrase, +10/token, ÷ `log2(max(len, 256))`; title +100 phrase, +20/token, unnormalised.
- `match_page(page, term_lower, kind) -> MatchedPage | None` — `name_match` plus matching lines.
- `search_extract(pages, queries, *, max_pages) -> dict[str, list[ExtractHit]]` and `search_match(pages, terms, *, kind, page_cap, hit_cap) -> dict[str, MatchResult]` — **both take a sequence of queries** and return one result per query. Ordering and caps are identical to today, including the two-bucket name/body split and path sort, but each query owns its own `name_pages` / `body_pages` / `hit_count` / `line_cap_reached` state. The scan's early exit generalises from "this query is saturated" to "every query is saturated".
- `rank_of(pages, queries, targets) -> dict[str, int | None]` in `evaluate.py` — a second **reducer** over the same `score_extract` / `match_page` functions. Where the engine accumulates capped result lists, this counts only how many pages outscore a named target, giving an exact rank in O(1) memory per query. That is what makes 916 simultaneous known-item lookups affordable: the engine's per-query result lists would cost ~183k entries, the reducer costs one integer each.

Drift risk lives entirely in `scoring.py`, which both consumers share. The reduction differs by design, and §4 verifies the two agree.

### 2.2 MCP server changes

`_wiki_search_extract` and `_wiki_search_match` become thin: resolve roots from `REPO_ROOT` → `scan_corpus` → engine → render text/JSON. Deliberately preserved:

- The `REPO_ROOT` monkeypatch seam at `server.py:58` — many existing tests depend on it.
- The `_hits` telemetry field on both handlers, including `match`'s "one row per matching line, or one per name-only page" rule (`#26`).
- Every reported flag: `truncated`, `budget_exhausted`, `skipped_oversize_files`.
- Byte-for-byte identical rendered output, held by the 245 existing tests that already exercise this surface (§4).

`_wiki_search_match` is deliberately reshaped to be multi-term internally, per the single-pass design above; its externally visible single-term contract is unchanged.

**One behaviour fix is required, not optional.** `_wiki_search_extract` sorts by score alone (`server.py:628`). Python's sort is stable, so equal scores fall back to insertion order — which is `rglob("*.md")` order, i.e. **filesystem order**, since `rglob` does not sort. Ordering is therefore not reproducible across machines whenever scores tie.

Measured on `demo/`: **199 of 203** title queries have a tie somewhere in their results, and one (`Cursor`, two pages at 125.5) has its **top two** tied — so which page "wins" is currently arbitrary.

The fix is to sort by `(-score, rel_path)`, matching what `_wiki_search_match` already does at `:880-881` and what `load_pages` does with `sorted()`. This decides only which of two *equally scored* pages comes first; it changes no score and no relative order of differently-scored pages.

It is in scope despite the functional spec excluding ordering changes, because #197's own acceptance criteria require *"Re-running the scorer on an unchanged tree is deterministic (no flakiness from dict/set iteration order — cf. #150)"*, and `title_ambiguity` cannot give a stable answer without it.

**Early exit under multiple queries.** Today the scan breaks out once the line cap is reached and the name-page cap is full. With N queries that condition becomes "every query has saturated", so a single-query call behaves exactly as before. `budget_exhausted` continues to describe the scan, which is what it already means.

This edge is **already covered** by existing tests — `test_search_reports_budget_exhaustion`, `test_search_budget_exhaustion_is_reported_under_a_kind_filter` and `test_search_within_budget_reports_a_complete_scan` in `tests/test_mcp_byte_cap.py`, plus five `test_read_capped_*` tests on the primitive. What is added (§4) is the multi-query case those tests do not reach.

### 2.3 New CLI command: `llmwiki search`

A plain search command. It does **not** interpret expectations, carries no `--expect` flag, and always exits 0 on a successful search — a term that is absent simply returns nothing. Verdict logic belongs to the linter (§2.4), which is the thing that holds ground truth.

| Flag | Purpose |
|---|---|
| `QUERY` (positional) | The term, or the phrase when `--mode phrase` |
| `--mode term\|phrase` | `term` → match mode; `phrase` → extract mode. Default `term` |
| `--terms-file PATH` | Bulk input, one entry per line; `#` comments and blanks skipped; `-` reads stdin |
| `--vault PATH` | Any vault, via the shared `--vault` definition at `cli.py:2526` and `_content_root(args)` |
| `--include-raw` | Also scan `raw/sessions/` |
| `--kind K` | Frontmatter `type` filter (match mode) |
| `--max-pages N` | Result cap (phrase mode) |
| `--format text\|json` | Same two shapes the MCP tool offers |

Bulk output groups results per entry and states plainly which entries returned nothing, so the two-pass workflow in R1 is readable by eye.

`cmd_query` (`cli.py:585`, graphify-only) is **not touched**.

### 2.4 Three lint rules

Registered normally via `@register` in `llmwiki/lint/rules/`, following the existing 17.

| Rule | Severity | Reports |
|---|---|---|
| `page_findability` | error | A titled page not returned at all when searched by its own title, and why (e.g. results cut short before reaching it) |
| `title_ambiguity` | warning | A titled page not ranked first for its own title — **naming the page that outranked it**, or reporting a tie when scores are equal |
| `search_consistency` | error | Search disagreeing with a literal scan, over wiki pages **and** session content; reports survival share as information |

**Order stability.** None of the three rules depends on top-5 ordering. `page_findability` asks only whether a page was returned at all; `search_consistency` asks only whether a result set was non-empty (present terms) or empty (absent terms) — which is why the verdict logic lives here rather than in `search`. Only `title_ambiguity` reads position, and only position 1, which the `(-score, rel_path)` tiebreak in §2.2 makes reproducible. Where the top two genuinely tie, the rule says so instead of naming an arbitrary winner: a tie is itself the duplicate signal the rule exists to surface.

**Corpus access without a new `run()` kwarg.** `LintOptions` (`lint/__init__.py:41`) travels on the rule *instance* and its docstring forbids adding a `run()` keyword — 16 of 17 rules would report a clean vault as 16 errors. So `LintOptions` gains fields instead, which is the sanctioned path:

- `content_root: Path | None` — the vault root, so `search_consistency` can reach `raw/sessions/`, which `load_pages` (`lint/__init__.py:125`) never exposes.
- `search_context: SearchContext | None` — a holder that scans **lazily and at most once per lint run** and is shared by all three rules. One scan total, no module-level cache, no staleness, lifetime bounded by the run.
- `findability_sample_max: int = 300` — see below.

The rules deliberately do **not** reuse lint's `pages` dict: `load_pages` skips `README.md` and applies no byte caps, so scoring over it would measure something subtly different from real search. They score over `scan_corpus` output, which is what search actually sees.

When both new options are absent — a rule constructed directly, as tests and the perf suite do — the rule reports itself **skipped** through `run_lint`'s existing skip channel rather than returning an empty list, so an unrunnable check never reads as a clean one.

**Sampling above a threshold.** Checking every page is O(pages²): 918² pairs at 9.5 µs is ~8 s, on a lint run already taking 20.8 s. So `page_findability` and `title_ambiguity` check every page up to `findability_sample_max` (300) and sample deterministically above it — roughly 2.6 s at the cap — and **state in their output** how many of how many were checked. Selection is evenly spaced over sorted page paths, giving uniform coverage with no RNG. The demo vault's 203 pages sit below the threshold, so the project's own verification (§2.7) always checks everything.

**Deterministic term selection for `search_consistency`.** No seeded RNG. Present terms come from the first and last `raw/sessions/` file by sorted filename, matched on `[A-Za-z][A-Za-z0-9_-]{5,}`, deduplicated, sorted, then sampled evenly to N (default 40 — the size measured at 40/40 agreement). Absent terms are generated from a fixed deterministic pattern and confirmed absent by scan, advancing deterministically on collision. Both groups are **printed in full**, per R3.

The rule runs both groups through the same search path, exactly as the MCP tool would: present terms must return results, absent terms must return nothing.

### 2.5 Demo session generator

`scripts/generate_demo_sessions.py` gains:

- **A `tool` turn role.** `Session.turns` is `tuple[tuple[str, str], ...]` with only `user`/`assistant` today, so R5's tool-output placement does not exist yet. The renderer (`:444-449`) emits `### Turn N — Tool` alongside the existing two.
- **A static planted-term table** keyed by `(session slug, placement)`. Static because the generator re-runs with a fresh `--today` on release cuts (`#225`) — terms derived from dates would move. Terms are invented but plausible subject matter, since the demo is published and read by evaluators.
- **Planted multi-word phrases as well as single terms**, so phrase mode is exercised rather than only term mode. A phrase is planted contiguously in exactly one placement, and is chosen so its individual words also occur separately elsewhere in the corpus — otherwise phrase mode's whole-phrase bonus is never actually under test, since any page containing the words would trivially be the only match.
- **Synthetic absent phrases** alongside synthetic absent terms, confirmed absent by scan.
- **Fixture emission** to `tests/fixtures/demo_search_terms.json`.

Placements are session title, user turn, assistant turn, and tool output, spread across the four adapters already present (`claude_code` 16, `cursor_cli` 6, `openclaw` 4, `codex_cli` 2).

### 2.6 Fixtures

| Path | Written by | Content |
|---|---|---|
| `tests/fixtures/demo_search_terms.json` | the generator | `present: [{value, kind: term\|phrase, session, placement, adapter}]`, `absent: [{value, kind}]` — both groups carry terms **and** phrases, so both search modes are covered |
| `tests/fixtures/demo_search_baseline.json` | a maintainer, deliberately | **Four numbers plus `_doc`** — see below |

Both are committed and human-readable, following the `tests/perf-budgets.json` precedent (a `_doc` key explaining what the file is and how to regenerate it). MRR is stored rounded to 6 decimal places so exact comparison is stable across platforms.

**What the baseline records, and why so little.** The governing rule is: *record only what cannot be derived.* Every recorded number is a number that churns when the demo corpus legitimately changes, so each one has to earn its place.

| Key | Why it is recorded |
|---|---|
| `mrr_extract` | Most sensitive single number to a ranking change; carries the whole rank distribution |
| `mrr_match` | Same, for the other mode — the two can regress independently |
| `rank1_extract` | Catches the top result specifically breaking, which MRR can mask: 13 pages slipping to rank 2 and one page slipping to rank 20 look similar in MRR, but only the former is a broad regression |
| `rank1_match` | Same, for the other mode |

Deliberately **not** recorded:

- **Found count and page total.** `found == total` is an *invariant*, asserted directly. Recording 203 twice would add churn on every demo page added or removed while catching nothing that the invariant does not.
- **Per-page ranks.** Maximum information, maximum churn — 203 entries that shift on any content edit. `title_ambiguity` already reports per-page detail to a human at lint time, which is where per-page detail belongs.
- **Wikilink-anchor lookup metrics.** Hundreds of lookups that change whenever any page edits its `## Connections` section. These are computed and reported, but not gated: gating them would fail builds for ordinary content edits, and the title-based known-item set already covers ranking regressions.

### 2.7 The project's own verification

`tests/test_197_acceptance.py`, matching the repo's `test_<issue>_acceptance.py` convention. It **reads only** — required by `ci.yml`'s "Working tree clean after tests" step (`git diff --exit-code`), which fails the build if a test modifies a tracked file.

Asserts, exactly and without tolerance:

- Every `present` entry is returned — terms through term mode, phrases through phrase mode.
- No `absent` entry returns anything, in either mode.
- Every titled demo page is findable by its own name (currently 203/203).
- MRR matches the recorded baseline exactly.

Reports without asserting: survival share, broken down by placement × adapter.

**Where that breakdown is published** (the spec's open question): printed by this test and recorded as a table in `docs/benchmarks.md`, updated deliberately when the demo corpus changes. It is maintainer-facing and has no user-facing home.

It rides the existing `lint-and-test` job. **No new CI job.**

### 2.8 Documentation

| File | Change |
|---|---|
| `docs/` user pages | `llmwiki search`: both modes, bulk input, `--vault`. Described as a pre-AI-era search engine — score-weighted matching of the literal characters typed, found anywhere including inside longer words (`cat` matches `concatenate`), no stemming, no spelling correction, no semantics. Current state only, no history |
| `docs/` lint page | The three rules by name, and the survival share as information rather than defect |
| `docs/benchmarks.md` | Findability section beside the speed and size tables, including the placement × adapter breakdown |
| `docs/maintainers/` | Rationale, the `DECLINED.md:224` reading, and why P@k/R@k/F1/nDCG were rejected as degenerate |

---

## 3. Impact and Risk Analysis

### System Dependencies

- `llmwiki/mcp/server.py` — the most-used agent surface; its output contract must not move.
- `llmwiki/lint/` — `LintOptions` gains fields; the 17 existing rules must be unaffected.
- `llmwiki/wikilinks.py` and `llmwiki/graph.py` — answer-key derivation reuses `build_page_alias_map` and `resolve_wikilink_target` rather than reimplementing resolution, so lookups and the graph view can never disagree.
- `scripts/generate_demo_sessions.py` and the committed `demo/` corpus; `docs/maintainers/RELEASE_PROCESS.md` re-runs it on release cuts.
- `.github/workflows/ci.yml` — consumed as-is, not modified.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Refactoring the busiest agent surface silently changes results.** Still the highest-consequence risk. | Already substantially covered: **245 tests across 13 files** exercise `wiki_search`, and ordering specifically is pinned by `_pages_in_order()` in `tests/test_mcp_enhanced.py`, `test_search_name_match_ranks_above_body_match`, and `test_search_json_format_keeps_the_documented_ranking`. The refactor must leave that suite green with no test edits — a test that needs changing is the signal that behaviour moved. A throwaway before/after comparison over `demo/` is a useful working aid during the refactor, but is **not** committed: a golden corpus would break whenever demo pages reorder, for reasons unrelated to search. |
| Per-query cap state leaks between queries in the multi-query pass — the genuinely new failure mode | Each query owns its accumulators; asserted by a test running N queries in one pass and comparing each result against the same query run alone |
| Lint gets slower (+~3 s at the sampling cap, on 20.8 s) | Single shared scan; sampling above 300 pages; all three rules individually skippable, like the existing 17 |
| Planted terms trip the privacy gate | `tests/test_privacy_username.py` scans tracked `*.md`/`*.py`. Terms are invented words chosen so they cannot resemble a real identifier; per `CLAUDE.md`, the forbidden list is read from CI rather than restated anywhere |
| Planted terms make the published demo look like test scaffolding | Plausible subject-matter words, one per session, reviewed by reading rendered transcripts |
| Baseline churns on unrelated demo edits | Expected and intended: demo changes are deliberate, and the baseline is updated as part of that change. Exact comparison is preferred over a tolerance that would hide a real regression |
| Fixture and demo corpus drift apart | The generator emits the terms fixture, so regenerating sessions regenerates it in the same commit |
| `LintOptions` growth affects existing rules | Additive fields with defaults; the frozen dataclass and instance-carried contract are unchanged; full suite is the check |
| Sampling makes lint output mean different things on different vaults | Every sampled run states how many of how many pages were checked |
| The `(-score, rel_path)` tiebreak changes ordering, which the functional spec excluded | Scoped as a determinism fix, not a ranking change: it reorders only pages with *identical* scores. Required by #197's own determinism criterion; recorded as an amendment to the functional spec's Out-of-Scope list |
| Planted phrases do not actually exercise the whole-phrase bonus | Phrase words are chosen to occur separately elsewhere in the corpus, so a page matching the whole phrase must beat pages matching only its words |

### Explicitly not addressed

Per-call search cost ([#244](https://github.com/AlexanderMakarov/llm-wiki/issues/244)) is untouched — §2.1 makes *checking* fast by scanning once, but a single MCP call still reads the whole corpus. The refactor does make an index cheaper to add later, since scanning is now isolated behind one function.

---

## 4. Testing Strategy

**The existing suite is the gate.** 245 tests across 13 files already cover this surface, including ordering (`_pages_in_order()` and the two documented-ranking tests in `tests/test_mcp_enhanced.py`), byte caps and budget reporting (`tests/test_mcp_byte_cap.py`), cold storage, page kinds, safety and telemetry. **The refactor must leave every one green without editing any of them.** A test that has to change is evidence behaviour moved, not evidence the test was wrong. No golden fixture is committed; an ad-hoc before/after diff over `demo/` during the refactor is a working aid, not an artifact.

**Multi-query isolation** — the new failure mode this design introduces. For a set of queries, assert that running them together in one pass yields, for each query, exactly what that query yields when run alone: same pages, same order, same `truncated` / `budget_exhausted` / `_hits`. Includes the saturation case, where one query fills its caps while others are still collecting, and a multi-query run at artificially reduced caps, which existing byte-cap tests reach only single-query.

**Unit** — scoring arithmetic against hand-computed values (the ÷`log2(max(len,256))` normalisation and the unnormalised title bonus are the parts worth pinning); `scan_corpus` cold-storage exclusion, per-file cap, aggregate budget, and both completeness flags at reduced caps; determinism of page sampling and of both term-selection paths, asserted by running twice and comparing.

**Integration** — `llmwiki search` for both modes, bulk input including stdin, `--vault` targeting a temp vault, `--format json`, and a not-a-vault path producing a clear error rather than a traceback. Each of the three lint rules on purpose-built temp vaults: a page unreachable by its own title, a page outranked by a near-duplicate, and a vault where search and a literal scan agree. Skip-reporting asserted when the new `LintOptions` fields are absent.

**Determinism** — extract-mode ordering asserted stable under tied scores by scoring a corpus with deliberately equal-scoring pages and checking the order is by path, plus a test that shuffling filesystem iteration order does not change results. This is the regression guard for the `server.py:628` defect.

**Acceptance** — `tests/test_197_acceptance.py` as described in §2.7, covering planted terms *and* planted phrases in both modes.

**Non-regression** — the full existing suite, especially MCP tests that monkeypatch `REPO_ROOT`; `ruff check llmwiki tests scripts`; and the clean-working-tree step, which will catch any test that writes where it should not.

**Reducer/engine agreement** — the R4 acceptance criterion says results must be *verified* identical to ordinary search, not assumed. `evaluate.rank_of()` reduces differently from the engine (§2.1), so a test asserts that over a small corpus the rank it reports for a target equals the target's index in the engine's own ordered results, for every query. This is the guard against the cheap reducer silently disagreeing with what a user would actually see.

**Not tested** — synthesis survival is measured at 78% and reported, never asserted. A test asserting it would fail on any legitimate change to demo content or synthesis prompts.

---

## 5. Specialist Coverage Gap

No Python specialist agent is registered in this environment (available: `Explore`, `Plan`, `general-purpose`, `feature-dev:*`, `pr-review-toolkit:*`, `code-simplifier`, `testing-expert`). Stack sections here were drafted directly. `testing-expert` covers the feature-level QA slice at implementation time. If a Python specialist is wanted for implementation review:

`/awos:hire cover 197-search-quality-eval: need Python 3.12 stdlib library design, CLI argparse surface design, pytest fixture strategy`
