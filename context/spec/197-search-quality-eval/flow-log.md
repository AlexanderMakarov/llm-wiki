# Flow log — 197-search-quality-eval

## fetch-ticket — done (2026-09-08)

- Source: GitHub Issue [#197](https://github.com/AlexanderMakarov/llm-wiki/issues/197), state `OPEN`, labels `enhancement` + `important`, no comments, no linked issues or attachments.
- Normalized: `TICKET_ID=197`; title "feat: measure search quality (precision/recall/F1/nDCG) and gate it in CI"; acceptance hints taken from the issue's own checklist.
- Next: resume-detection.

## resume-detection — done (2026-09-08)

- Not already delivered: issue `OPEN`; no `context/spec/*197*` directory; no `tests/fixtures/search_eval*`; no `scripts/eval_search.py`; no `search-quality` job in `ci.yml`; `gh pr list --search 197` empty.
- No `flow-log.md` existed, so nothing to resume — started from `fetch-ticket`.
- Next: workspace.

## workspace — done (2026-09-08)

- Worktree `.claude/worktrees/feat-197-search-quality-eval` on branch `feat/197-search-quality-eval` from `origin/main` @ `cf87055`.
- `LLMWIKI_SKIP_AUTOMATION=1 ./setup.sh` ran clean; throwaway vault at `<WT>/.worktree-vault` initialised; worktree `config.json` points at it. Absolute paths used per delivery-flow §10 (#213).
- `context/product/architecture.md` readable. Working tree was clean at start.
- Next: specs.

## research (pre-spec) — done (2026-09-08)

Findings that materially reshaped the feature, all verified in the worktree at `cf87055`:

- **Issue's surface table is stale.** #196 already shipped — there is no separate `wiki_query` tool. `llmwiki/mcp/server.py:237` exposes one `wiki_search` with `mode=match|extract|filter`; the ex-`wiki_query` ranking survives as `_wiki_search_extract` (`server.py:554`). The "#197 blocks #196" motivation is retrospective.
- **`demo/wiki/` has no `archive/`**, so the issue's archived-page acceptance criterion had nothing to point at.
- **Palette `score()` (`llmwiki/render/js.py:968`) is not fuzzy** — no edit distance — so the issue's "misspellings (palette fuzzy only)" class would score zero everywhere.
- **`docs/maintainers/DECLINED.md:224`** declines an "Eval framework / `llmwiki eval` subcommand": *"Do not reintroduce a scoring CLI unless it is a real subcommand with tests."* Roadmap line 42 records the same (#154) — CI once ran a no-op behind `|| true` and reported success while measuring nothing.
- **`DECLINED.md:88`** declines a Node runtime dependency ("would destroy the 'stdlib Python plus `markdown`, no Node runtime' promise"), which collided with the issue's *preferred* Node runner for the palette.
- **Ranking has only two knobs, and page naming dominates.** In `_wiki_search_extract` a title hit scores +100 unnormalised while a body score of 50 is divided by `log2(max(len,256))` ≈ 13 for a typical page — roughly **25× in favour of the title**. `_wiki_search_match` has no score at all: two buckets (name/path match, body-only), each sorted by path. So retrieval quality is dominated by whether the page exists and what synth named it — i.e. by how the wiki is *built*.
- **No index.** `_iter_scan_files` (`server.py:735`) `rglob`s all of `wiki/` per call. Measured on a ~900-page vault: `match` 421 ms / 882 files / 2.4 MB; `match --include_raw` 688 ms / 1,622 files / 26.7 MB; `extract` 180 ms. Filed separately as [#244](https://github.com/AlexanderMakarov/llm-wiki/issues/244) — performance, not quality.
- **Demo generator axes** (`scripts/generate_demo_sessions.py`): 28 authored sessions, adapters `claude_code` 16 / `cursor_cli` 6 / `openclaw` 4 / `codex_cli` 2, across 7 projects. Turns are `(role, text)` with roles user/assistant only — no distinct tool-output turn type today.

## specs — in progress (2026-09-09)

- `functional-spec.md` written. Spec dir uses the repo's issue-number convention (`197-…`), not `create-spec-directory.sh`'s sequential index, matching existing siblings (`227-…`, `234-…`).
- Decisions taken with the user during the spec interview:
  1. **Palette and site are out.** Measurement is for maintenance of MCP answer quality only; nothing built into the static site. Sidesteps the `DECLINED.md:88` Node collision. Drops the issue's "all three surfaces" criterion.
  2. **Archived-page case dropped** — no `demo/wiki/archive/` to point at; deferred.
  3. **Ground truth is derived from the vault**, not hand-labelled: page titles as known-item queries, and `[[wikilink]]` anchors as queries whose answer is the resolved target, reusing `graph.py`'s resolver + alias map. Plus a small hand-written in-repo set for no-answer / common-token / misspelling classes.
  4. **Graph data is an input only** — no changes to `graph.html` or any generated page.
  5. **Planted sentinel terms** in `generate_demo_sessions.py` at known placements (session title, user turn, assistant turn, tool output) × agent tool, so the report cross-tabs survival-through-synthesis. Constrained by: published demo must stay plausible, CI's forbidden-string grep, and generator determinism across release re-runs.
  6. **Harness is a pytest test** in the existing suite (no new `ci.yml` job), plus a maintainer script accepting an explicit vault path. MCP root is repointed via the documented `server.py:58` test seam.
  7. **Calibration is a one-off**, reported not committed: degrade ranking → re-measure → report → thresholds chosen from that evidence.
  8. **Both `wiki_search` modes** measured (`extract` and `match`).
- Filed [#244](https://github.com/AlexanderMakarov/llm-wiki/issues/244) at the user's request during this stage (perf / no index / 50 MB cap as correctness cliff).
- Next: user approval gate on `functional-spec.md`, then `/awos:tech`.

## specs — spec revised after second review round (2026-09-09)

User review of the first `functional-spec.md` draft raised four points; all four were investigated in code and all four changed the spec.

- **"Why hand-written *questions*?"** — correct challenge. `mode=match` takes `term` (literal substring, no tokenisation); only `mode=extract` takes `question`. R2 rewritten as **two supplied term lists** (must-be-found / must-not-be-found), which fits both modes and is now offered for any vault, not just the demo.
- **"Why maintainer-only?"** — correct. Derived ground truth is vault-agnostic, so the capability is user-facing. This makes it a real CLI command, which `DECLINED.md:224` explicitly permits ("unless it is a real subcommand with tests") rather than forbids. Spec now takes that escape clause deliberately and R8 requires documenting why.
- **"How hard to put this in `lint`? Maybe a new CLI tool — `query` is graphify-only."** — split into two, per user's "both" answer:
  - **New command** (R4) for the corpus-level metrics. `cmd_query` (`cli.py:585`) is graphify-only and errors without `pip install llmwiki[graph]`; user chose a new name over repurposing it, so `query` keeps its contract.
  - **Lint rule** (R6) for the per-page signal "page not retrievable by its own title", which genuinely fits lint's per-page issue shape (`{rule, severity, page, message}`). Note `load_pages` (`lint/__init__.py:125`) loads `wiki/` only — no raw access — which is why the raw→MCP round-trip lives in the command, not the rule.
- **"Won't calling MCP for every page be very slow?"** — legitimate, and measured on the live 918-page vault:
  - one `wiki_search` per page title = **6.4 min**
  - one corpus read (210 ms) + in-memory scoring of all 916 lookups = **~8 s** (9.5 µs per page-query pair, 840,888 pairs)
  - existing `llmwiki lint` on the same vault already takes **20.8 s**, so the R6 rule is proportionate.
  - Became **R5**, with the hard constraint that the batch path must reuse the *same* scoring code as the live tool (extract per-page scoring from the corpus walk) — a second copy would drift, the failure mode already rejected for the palette.
- **"How does in-browser search compare to MCP?"** — investigated; they index **near-disjoint corpora**. Built the demo: `search-index.json` has 336 meta + 28 session entries (176 document, 97 docs, 35 topic, 15 slash, 7 project, 6 page) and **zero** pointing at `wiki/entities`, `wiki/concepts` or `wiki/sources`; the built site has no `entities/`/`concepts/` directory, and `build.py:2474` reads `wiki/entities/` only for the AI-model directory page. Filed as [#248](https://github.com/AlexanderMakarov/llm-wiki/issues/248) at the user's request and cited in Out-of-Scope so the browser exclusion reads as reasoned.

Spec grew from 7 requirements to 8 (R4 command, R5 performance, R6 lint rule are new; old R5 folded into R4).

- Next: user approval gate on the revised `functional-spec.md`, then `/awos:tech`.

## specs — third revision (2026-09-10)

User raised 11 points on the second draft. All applied; two required measurement first.

Corrections accepted verbatim:
- **`llmwiki search`, not a report command.** Two modes (term / phrase), output shaped like `wiki_search` — a results list, not a metrics table. Name settled: `search`.
- **One term list per invocation**, not two. User runs it once with should-find terms, again with should-not-find.
- **No project-kept term-list fixture.** Automatic checks derive everything; bulk term input is a *feature of `search`* for manual checking.
- **"Health check" = `lint`.** Said plainly now, in both new rules.
- **`lint` (user feature) vs repo pytest (our regression protection) are separate**, and no longer reference each other.
- **"Runs against a vault it has never seen" was vacuous** — search is deterministic and stateless. Dropped.
- **No history in user docs**; rationale/alternatives move to maintainer docs.
- **`k=10` dropped** — no product grounding. `k=5` kept because `extract` defaults to `max_pages=5`; `k=1` kept as "does the top hit answer".
- **Document `search` as pre-AI-era search-engine behaviour**: score-weighted matching of literal characters, found anywhere including inside longer words (`cat` matches `concatenate`) — no stemming, no spelling correction, no semantics.

Measured before answering "do we need thresholds at all?" (user's claim: any not-found is an error):

| vault | titled pages | found at all | rank 1 | in top 5 | `truncated` |
|---|---|---|---|---|---|
| demo (full) | 203 | **203/203** | 190 | 202 | — |
| live (150 sampled of 916) | 916 | **150/150** | 142 | 150 | 0/150 |

Conclusion — the claim splits in two, and only one half is zero-tolerance:
- **Found-at-all → error, no tolerance.** Near-structural: a title query scores its own page +100 for the phrase in its own title, so it cannot score zero. 353/353 across both vaults. A failure means the 200-page cap bit, a file was unreadable, or scoring changed. → **R3**.
- **Rank-1 → warning, not zero-tolerance.** ~5-6% legitimately fail, and inspection shows the *vault* at fault, not search: `Configuration` loses to `Configuration Reference` (title is a substring); `Wikilinks` loses to a `wikilinks` candidate (case-collision duplicate — same class as commit `01ae2ae`); `llmwiki` sits at rank 16 (token in everything). The page that outranked it is the actionable output — free duplicate detection. → **R4**.
- **Thresholds eliminated entirely, as the user wanted.** Demo is committed and search deterministic, so R7 snapshots the *exact set* of 13 not-ranked-first pages rather than a count or a tolerance. Any change either way fails; a person updates the snapshot deliberately. Exact, flake-immune.

Deliberate departure from #197's metric list, recorded in R7 and Out-of-Scope: **P@k / R@k / F1 / nDCG are degenerate here.** Every derived lookup has exactly one correct answer (a title names one page; a wikilink anchor resolves to one target), so precision and recall collapse to "is the answer at rank ≤ k" and nDCG reduces to `1/log2(rank+1)`. Reported instead: found-rate, rank-1 rate, MRR (cutoff-free, carries the whole rank distribution).

Spec restructured to 8 requirements: R1 `search` command, R2 derived answer key, R3 lint error, R4 lint warning, R5 performance + shared scoring, R6 planted terms, R7 exact repo tests, R8 docs.

- Next: user approval gate on the third draft, then `/awos:tech`.

## specs — fourth revision, approved to proceed (2026-09-10)

User raised 4 points and said "proceed". Applied:

- **R1 — bulk lists of *phrases* too**, not only terms. Both modes take single or bulk input, one list per run.
- **R3 — check session content, not just page names.** New `search_consistency` check: sample real terms out of the vault's own `raw/` sessions, generate synthetic never-occurring terms, establish presence by literal scan, require search to agree exactly. Every term used is shown to the operator. This is the "automatic health measurement via lint" the user asked for.
- **R6/R7 — verification runs in CI, so nothing can be written or committed at run time.** Both term groups are produced by the generator (R5) and kept with the project; verification only reads them and never re-scans the vault.
- **R8 — name the checks exactly.** Three, not two.

Measured on demo before writing, because the naive form of R3 would have failed constantly:

| check | result |
|---|---|
| grep ⟺ `search` agreement (40 sampled raw terms, `include_raw`) | **40/40**, zero disagreements |
| synthetic negatives, grep-confirmed absent | **5/5** absent, 0 wrongly returned |
| raw terms surviving synthesis into `wiki/` | **78%** (31 survive, 9 lost) |

→ Decisive split: **grep-vs-search agreement is an error rule** (100% today, any disagreement is a real bug — cap truncation, encoding, archive exclusion). **Synthesis survival is a reported number, never a failure** — at 78%, an error rule would fail on ~22% of terms because synthesis summarises rather than preserves. Conflating them would have shipped a permanently-red check. The survival rate is also the first visibility into how much the pipeline drops.

Final check names (no collision with the 17 existing rules):
- `page_findability` — **error** — titled page not returned when searched by its own title.
- `title_ambiguity` — **warning** — page not first for its own title; message names the page that outranked it.
- `search_consistency` — **error** — search disagrees with a literal scan over wiki pages *and* session content; reports survival share as information.

Dropped from the previous draft: the "exact set of 13 not-ranked-first pages" snapshot. `title_ambiguity` is warning-level vault-quality signal and pinning that set in CI would fail on every legitimate demo content edit. R6 instead asserts exact MRR, which catches a ranking regression precisely without churning on page-set changes.

Spec is 7 requirements: R1 `search`, R2 derived answer key, R3 three health checks, R4 performance + shared scoring, R5 generator-produced term groups, R6 exact CI verification, R7 docs.

- Next: `/awos:tech`.

## tech — done (2026-09-10)

`technical-considerations.md` written. No `Explore` subagent dispatched: the exploration was already in context with real measurements, and re-deriving it cold would cost more than it returns (user CLAUDE.md prefers the cheaper path). No Python specialist agent is registered in this environment — stack sections drafted directly and the gap recorded in §5 with a pre-filled `/awos:hire` line.

Decisions taken at this stage:
1. **New root-agnostic `llmwiki/search/` package** (`corpus.py` / `scoring.py` / `engine.py` / `evaluate.py`). The engine takes an *iterable of scanned pages*, so it cannot distinguish a fresh scan from a cached list — batching needs no second code path and drift is impossible by construction rather than test-prevented. No import-time state, which confines `mcp/server.py`'s import-time `CONTENT_ROOT` binding to the MCP layer and is what makes `--vault` work for CLI and lint.
2. **`llmwiki search` is a pure search command** — user correction. No `--expect`, always exits 0; an absent term simply returns nothing. Verdict logic lives in the linter, which holds the ground truth and runs both term groups through the same search path. `cmd_query` untouched.
3. **Lint sampling above a threshold** (user's choice): `page_findability` / `title_ambiguity` check every page up to `findability_sample_max`=300 and sample evenly above it, stating "n of N checked". ~2.6s at cap vs ~8s full, on a 20.8s baseline. Demo (203 pages) is below the threshold, so CI always checks everything.
4. **`LintOptions` gains fields** (`content_root`, `search_context`, `findability_sample_max`) — the sanctioned path, since its docstring forbids a new `run()` kwarg (16 of 17 rules would report a clean vault as 16 errors). `SearchContext` scans lazily once per lint run, shared by all three rules. Rules report **skipped** via `run_lint`'s existing skip channel when options are absent, so an unrunnable check never reads as clean.
5. **Rules do not reuse lint's `pages` dict** — `load_pages` skips `README.md` and applies no byte caps, so scoring over it would measure something different from real search.
6. **Deterministic selection with no RNG** — page sampling is evenly spaced over sorted paths; present terms come from the first and last `raw/sessions/` file by sorted name, deduped/sorted/evenly sampled to 40; absent terms from a fixed pattern, advanced deterministically on collision. Both groups printed in full.
7. **Generator gains a `tool` turn role** — `Session.turns` has only user/assistant today, so R5's tool-output placement did not exist. Planted terms live in a **static** table because the generator re-runs with a fresh `--today` on release cuts (#225).
8. **Fixtures**: `tests/fixtures/demo_search_terms.json` (generator-written) and `tests/fixtures/demo_search_baseline.json` (maintainer-written, MRR rounded to 6dp for cross-platform exactness), both following the `tests/perf-budgets.json` `_doc` precedent.
9. **Open question closed**: the placement × adapter survival breakdown is printed by `tests/test_197_acceptance.py` and recorded in `docs/benchmarks.md` — maintainer-facing, no user-facing home.

New CI constraints confirmed this stage, both binding R6:
- `ci.yml` has a **"Working tree clean after tests"** step (`git diff --exit-code`) — verification may only read prepared fixtures, never write.
- The privacy gate is `tests/test_privacy_username.py`, scanning tracked `*.md`/`*.py`; planted terms must be invented words that cannot collide with it.

**Hard task-ordering constraint recorded in §3/§4:** golden outputs of the current MCP search must be captured and committed as the **first** task, before any refactoring — after the refactor the old behaviour is unrecoverable and the change becomes unverifiable.

Risk flagged in §2.2: `_wiki_search_match` breaks out of the *scan* early once caps fill, so with a materialised scan `budget_exhausted` must be derived from the scan rather than the query loop. Only reachable on a corpus large enough to exhaust the 50 MiB aggregate budget; covered by a test at artificially reduced caps.

- Next: `/awos:tasks`.

## tech — revised after user review (2026-09-10)

Two challenges, both correct, both changed the design.

**1. "Why goldens if we're only refactoring?"** — over-engineering on my part, withdrawn. Evidence gathered: **245 tests across 13 files** already exercise `wiki_search`, and ordering specifically is pinned by `_pages_in_order()` (used across ~12 assertions in `tests/test_mcp_enhanced.py`), `test_search_name_match_ranks_above_body_match`, and `test_search_json_format_keeps_the_documented_ranking`. The `budget_exhausted` edge I had flagged as the top risk is likewise already covered by `test_search_reports_budget_exhaustion`, `test_search_budget_exhaustion_is_reported_under_a_kind_filter`, `test_search_within_budget_reports_a_complete_scan`, plus five `test_read_capped_*` tests on the primitive.
→ **No committed golden fixture.** A golden corpus would break whenever demo pages reorder, for reasons unrelated to search. The gate is instead: *the refactor must leave the existing suite green with no test edits* — a test needing a change is the signal that behaviour moved. A throwaway before/after diff during the refactor stays a working aid, not an artifact. The "capture goldens first" hard task-ordering constraint recorded in the previous entry is **retracted**.

**2. "`_wiki_search_match` must serve multiple items without re-iterating."** — accepted; this replaces the engine contract. Previous design was scan-once-then-call-engine-N-times over a materialised list. New design is **multi-query in a single pass**: each page visited once, every pending query evaluated against it, each query owning its own cap accumulators (`name_pages` / `body_pages` / `hit_count` / `line_cap_reached`). Single-query search is the N=1 case, so still one implementation.
- Engine signatures become `search_extract(pages, queries, …) -> dict[str, list[ExtractHit]]` and `search_match(pages, terms, …) -> dict[str, MatchResult]`.
- Scan early-exit generalises from "this query saturated" to "every query saturated".
- Motivation beyond elegance: materialising held the whole corpus in memory — 2.4 MB wiki doubles once lowercased, and `include_raw` turns 26.7 MB into ~53 MB on a large vault.
- Added `evaluate.rank_of()` as a **second reducer** over the same `scoring.py` functions: it counts only how many pages outscore a named target, giving exact rank in O(1) memory per query. Needed because 916 simultaneous known-item lookups through the engine's capped result lists would cost ~183k entries. Drift risk stays confined to `scoring.py`, which both consumers share.

Risk table and testing strategy updated accordingly. New top risk is **per-query cap state leaking between queries** — the genuinely new failure mode — tested by asserting each query's multi-query result equals its solo result (pages, order, `truncated`, `budget_exhausted`, `_hits`), including the saturation case and a multi-query run at reduced caps. New test: **reducer/engine agreement**, asserting `rank_of()`'s rank equals the target's index in the engine's own ordered results.

- Next: `/awos:tasks`.

## tech — second revision (2026-09-10)

Three user questions; the second uncovered a real defect.

**1. "What should `demo_search_baseline.json` include and how much?"** — governing rule written into §2.6: *record only what cannot be derived*, because every recorded number churns when the demo legitimately changes. Settled on **four numbers plus `_doc`**: `mrr_extract`, `mrr_match` (most sensitive single numbers to a ranking change, carry the whole rank distribution) and `rank1_extract`, `rank1_match` (catch the top result specifically breaking, which MRR can mask — 13 pages slipping to rank 2 and one page slipping to rank 20 look alike in MRR). Explicitly not recorded: found count and page total (`found == total` is an *invariant*, asserted directly — recording 203 twice adds churn and catches nothing extra); per-page ranks (203 entries, churn on any edit — per-page detail belongs in `title_ambiguity`'s lint output); wikilink-anchor metrics (hundreds of lookups that move whenever a `## Connections` section is edited — computed and reported, never gated).

**2. "How will the linter check phrase mode if page order changes and top-5 varies?"** — investigation found a genuine determinism bug, now in scope:
- `_wiki_search_extract` sorts by score alone (`server.py:628`). Python's sort is stable, so **ties fall back to insertion order = `rglob("*.md")` order = filesystem order** (`rglob` does not sort). `_wiki_search_match` sorts by path at `:880-881`, and `load_pages` uses `sorted()` — extract is the only one that does not.
- Measured on demo: **199 of 203** title queries have a tie somewhere in their results; **1** (`Cursor`, two pages at 125.5) has its **top two** tied — and that page is one of the `title_ambiguity` failures measured earlier, so its "which page outranked it" answer is currently arbitrary and machine-dependent.
- Fix: sort by `(-score, rel_path)`. Reorders only *equally scored* pages; no score changes, no relative order of differently-scored pages changes.
- **In scope despite the functional spec excluding ordering changes** — #197's own acceptance criteria demand determinism ("no flakiness from dict/set iteration order — cf. #150"), and `title_ambiguity` cannot answer stably without it. Recorded as an explicit **Amendment** section in `functional-spec.md` rather than silently widening scope.
- Answer to the question itself: **nothing in the linter depends on top-5 ordering.** `page_findability` asks only "returned at all"; `search_consistency` asks only "non-empty / empty" — which is exactly why the verdict logic was put in the linter. Only `title_ambiguity` reads position, and only position 1. Where the top two genuinely tie it now reports the tie instead of naming an arbitrary winner — a tie *is* the duplicate signal the rule exists to surface.

**3. "Generator should plant phrases too, not just terms."** — accepted. Both fixture groups (`present` and `absent`) now carry `kind: term|phrase`, so phrase mode is exercised rather than only term mode. Added constraint: each planted phrase's individual words must also occur separately elsewhere in the corpus — otherwise the whole-phrase bonus is never under test, since any page containing the words would trivially be the only match. Synthetic absent phrases added alongside absent terms.

Also updated: `title_ambiguity` tie reporting (§2.4), a new "Order stability" paragraph in §2.4 explaining why the three rules are order-independent, fixture shape (§2.6), acceptance assertions covering both modes (§2.7), two new risk rows (tiebreak-as-scope-change; phrases not exercising the bonus), and a **Determinism** test group covering the `server.py:628` regression.

- Next: `/awos:tasks`.

## tech — approved by user (2026-09-10)

User resumed `/implement-feature` with: technical-considerations look good — start with them. Status set to Approved on `functional-spec.md` and `technical-considerations.md`.

- Next: `/awos:tasks`.

## tasks — done (2026-09-10)

`tasks.md` written (implement-feature suppresses draft Approve ask). Six slices:

1. Extract `llmwiki/search/` + MCP rewire + deterministic tiebreak
2. `llmwiki search` CLI
3. Three lint rules + `SearchContext` / `LintOptions`
4. Demo planted terms/phrases + fixtures + `test_197_acceptance`
5. Docs / CHANGELOG / reference rows
6. Feature Testing & Regression (`testing-expert`)

All implementation tasks → `general-purpose` (no Python specialist hired). QA → `testing-expert`. Informational only — not a blocking gate.

- Next: commit-specs, then `/awos:implement`.

## commit-specs — done (2026-09-10)

- Commit `3ea7d6e` (after rebase: was `05ac075`) — `docs: add spec for #197 search quality and findability checks`.
- Rebased onto `origin/main` @ `7bc1391` before implement.
- Next: `/awos:implement`.

## implement — started (2026-09-10)

- Delegating Slice 1 tasks via coding subagents in worktree.

## implement — Slice 1 done (2026-09-10)

- `llmwiki/search/` package + MCP thin handlers + `tests/test_search_package.py` (16).
- Full suite 5104 passed; ruff clean. Existing MCP tests untouched.
- Intentional: extract title scoring via frontmatter; match scan completes then engines (budget_exhausted = scan).
- Next: Slice 2 CLI.

## implement — Slices 2–3 done (2026-09-10)

- Slice 2: `llmwiki search` CLI + `tests/test_cli_search.py` (11) + minimal `docs/reference/cli.md` row.
- Slice 3: three lint rules + `SearchContext` / `LintOptions`; demo disables `title_ambiguity` for known near-duplicates; findability ranks wiki-only.
- Next: Slice 4 fixtures + acceptance.

## implement — Slice 4 done (2026-09-10)

- Generator plants terms/phrases + tool turns; fixtures `demo_search_terms.json` / `demo_search_baseline.json`; `tests/test_197_acceptance.py`.
- Baseline on demo: mrr_extract 0.965825, mrr_match 0.970443, rank1_extract 0.935961, rank1_match 0.940887 (203 pages).
- Planted survival into wiki = 0% until demo resynth — reported only.
- Next: Slice 5 docs.

## implement — Slice 4 done (2026-09-10)

- Generator plants terms/phrases + tool turns; fixtures `demo_search_terms.json` / `demo_search_baseline.json`; `tests/test_197_acceptance.py`.
- Baseline on demo: mrr_extract 0.965825, mrr_match 0.970443, rank1_extract 0.935961, rank1_match 0.940887 (203 pages).
- Planted survival into wiki = 0% until demo resynth — reported only.
- Next: Slice 5 docs.

## implement — all slices done (2026-09-10)

- Slices 1–6 complete in `tasks.md`. Suite green (~5188 collected). Uncommitted implementation still in worktree.
- Slice 6 used `general-purpose` after `testing-expert` hit a usage limit.

## verify — done (2026-09-10)

Evidence against R1–R7:
- R1: `llmwiki search` on demo returns JSON pages; CLI tests + CLI↔MCP parity regression.
- R2–R4: lint rules + SearchContext; demo lint `page_findability`/`search_consistency` → 0 errors; survival info printed.
- R5–R6: fixtures + `test_197_acceptance.py` exact baseline.
- R7: docs + CHANGELOG + reference coverage green.
- Spec Status → Completed.
- Next: user smoke confirm (Step 8), then local review.

## smoke feedback — match preview fix (2026-09-10)

User found term-mode line previews hid the hit on long tags lines (`[:200]` from start). Fixed: `match_line_preview` keeps 150 chars before + 150 after the term. Phrase mode already used centred `extract_snippet` (~400 chars) — that is why it looked longer. Still awaiting overall smoke confirm for local review.

## smoke feedback — unify snippet helper (2026-09-10)

User asked both modes to use phrase-style `extract_snippet` (~400 centred). Removed `match_line_preview`; term-mode matching lines now call `extract_snippet` with the same default. Structure unchanged: term → lines, phrase → page snippet.

## local-review — smoke confirmed (2026-09-11)

User confirmed live-vault `llmwiki search` works (including centred snippet fix). Dispatching independent local review on `origin/main...HEAD`.

## local-review — written (2026-09-11)

- Review file: `context/spec/197-search-quality-eval/review.md` (gitignored, session-only).
- Verdict: Request changes — 2 Blockers, 3 Nits.
- Next: user keep/drop.

## local-review keep/drop (2026-09-11)

User: explain B2; elevate N1→blocker and fix; amend N2 tech for extract_snippet; N3 no action. B1 not decided yet.

- N1 fixed: `iter_scanned_pages` + MCP/CLI term streaming; saturation break after page; test asserts one file read when caps fill.
- N2: tech §2.2 amended (shape/ranking preserved; snippets via shared extract_snippet).

## local-review — B1 + B2 fixed (2026-09-11)

- **B2:** `select_present_terms(pages)` tokenises first/last scanned raw pages only (no unbounded `Path.read_text`); regression for oversize-skipped sessions.
- **B1:** `collect_wikilink_lookups` + graph `build_page_alias_map` / `resolve_wikilink_target`; `page_findability` samples lookups, info count, errors name anchor + target; cold archive excluded via scan.

## local-review keep/drop — B1+B2 fixed (2026-09-11)

User asked fix both blockers then re-review.
- B2: `select_present_terms(pages)` from scanned raw pages only.
- B1: wikilink lookups via alias map + resolve in `page_findability`.
- Next: local review pass 2.

## local-review pass 2 — written (2026-09-11)

- Review file: `context/spec/197-search-quality-eval/review.md`
- Verdict: Request changes — 1 Blocker, 2 Nits (prior B1/B2/N1/N2 marked resolved).
- Next: user keep/drop.

## local-review pass 2 — keep all applied (2026-09-12)

User chose fix-all (1).
- Rebased onto `origin/main` (includes #249); CHANGELOG keeps #249/#229 verbatim + #197 bullets.
- N1: bare wikilink path already used `search_match`; added `test_page_findability_bare_wikilink_uses_corpus_cap`.
- N2: unused `content_root` already dropped.
- Next: static gate, commit-push, remote gates.

## review feedback — demo generator (2026-09-12)

User asked to drop SEARCH-FINDABILITY.md (DECLINED note only), stop duplicating findability numbers in docs/benchmarks.md, rename `test_197_*` → feature names, and harden demo session generation:
- In-place-by-slug writes (option B): filenames stick; `--today` only moves frontmatter dates.
- Bodies match `llmwiki.convert` (shared turn index, `**Tools used:**` / `**Tool results:**`); activity profiles vary `user_messages` (1…15) so the sessions index is not a flat MSGS=2.
- Plants apply after expansion so short profiles cannot drop tool plants; `demo_search_terms.json` still emitted every run.

## follow-up (2026-09-12)

- Filed #255: demo Pipeline state on GitHub Pages should match a real vault (state gitignored → Pages shows full backlog).
- Eval on updated sessions: 20/20 plants found in raw (0% wiki survival until session re-synth); wiki title MRR/rank1 still equals baseline (wiki unchanged); raw session title known-item MRR/rank1 = 1.0.

## DRY — MCP search caps (2026-09-12)

- `_MCP_SCAN_PER_FILE_BYTES` / `_MCP_SCAN_AGGREGATE_BYTES` / `_SEARCH_HIT_CAP` / `_SEARCH_PAGE_CAP` now alias `llmwiki.search` defaults; literals live only in `corpus.py` / `engine.py`. Nearby check: CLI already imported the shared defaults; `PAGE_CAP_FOR_FINDABILITY` remains a named alias of `DEFAULT_PAGE_CAP` for lint monkeypatches.
