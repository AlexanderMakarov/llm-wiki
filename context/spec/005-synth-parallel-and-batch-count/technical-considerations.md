# Technical Specification: Synth batch count and parallel page synthesis

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (approved) — GitHub Issue [#118](https://github.com/AlexanderMakarov/llm-wiki/issues/118)
- **Status:** Completed
- **Author(s):** AWOS `/implement-feature` (agent)

---

## 1. High-Level Technical Approach

`llmwiki/synth/pipeline.py::synthesize_new_sessions` already separates *deciding what to synthesize* (building `new_items`) from *doing it* (the `for it in new_items:` loop). Only the second half changes.

The strategy has three parts:

1. **Make the per-source work pure.** Extract the loop body into a worker that does only the two things that must happen per source — call the backend and write that source's page file(s) — and returns a result record. The worker touches no shared counters, writes no state, and prints nothing.
2. **Let the orchestrator own everything shared.** Run the workers on a `concurrent.futures.ThreadPoolExecutor` and consume them with `as_completed`. Every mutation that was racy — the in-memory `state` dict, `_save_state`, the pending-state drop, `summary` counters, the `producers` tally, and stdout — happens in the main thread, one completion at a time. Most of the concurrency problem is removed by structure rather than by locking.
3. **Plumb one number through.** A `concurrency` parameter on `synthesize_new_sessions`, resolved from CLI option → saved config → default 2. Because the parameter and the start-of-run print live inside the pipeline function, all three call sites (`cli.py` ×2 and `pipeline.py`'s `all --with-synth`) inherit the behavior without duplicating logic.

Threads, not processes: both real backends block on I/O (`subprocess.run` for `claude -p`, `urlopen` for Ollama), which releases the GIL. No new runtime dependency — `concurrent.futures` and `threading` are stdlib.

**Systems affected:** `llmwiki/synth/pipeline.py` (main change), `llmwiki/synth/reporting.py` (start-of-run line), `llmwiki/synth/claude_cli.py` (usage-accumulator lock), `llmwiki/synth/base.py` (thread-safety contract in the ABC docstring), `llmwiki/cli.py` (new option + pass-through), `docs/reference/cli.md`, `docs/configuration-reference.md`, `CHANGELOG.md`.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Configuration

One new key, following the existing `synthesis.*` convention read by `resolve_backend`.

| Section | Key | Type | Default | Purpose |
| --- | --- | --- | --- | --- |
| `synthesis` | `concurrency` | int | `2` | How many source pages are synthesized at once. `1` restores strictly sequential behavior. |

Resolved by a new `resolve_synth_concurrency(cfg) -> int` in `llmwiki/synth/pipeline.py`, sitting beside `resolve_include_subagents` / `resolve_exclude_headless` and reading the same merged `config.json` + `sessions_config.json` map via `_load_sessions_config()`.

**Validation split** (deliberate, matching existing precedent):

- **Config values are tolerant.** A non-integer or out-of-range value falls back to the default and emits a `logging` warning naming the accepted range — the same tolerance `resolve_backend` applies to a bad `synthesis.backend`, so a typo in `config.json` can never crash an automated `sync`/`synth`. A **missing** key falls back to the default silently: the key is absent from every stock config, and llmwiki calls no `logging.basicConfig`, so `logging.lastResort` would put that warning on the stderr of every operator who never touched the setting.
- **CLI values are strict.** `--concurrency` is validated at parse time and a bad value exits `2` with a message naming the accepted range, because a hand-typed flag that was silently ignored is worse than a refusal.

**Accepted range:** `1 … MAX_SYNTH_CONCURRENCY` (16). The ceiling exists because the number bounds concurrent `claude -p` **subprocesses**; an unbounded value on a large backlog would fork a process per worker. Values above it are clamped with a warning (config) or rejected (CLI).

### 2.2 New and changed code

| Path | Change | Responsibility |
| --- | --- | --- |
| `llmwiki/synth/pipeline.py` | new `DEFAULT_SYNTH_CONCURRENCY = 2`, `MAX_SYNTH_CONCURRENCY = 16`, `resolve_synth_concurrency(cfg)` | Resolve + normalize the saved preference |
| `llmwiki/synth/pipeline.py` | new module-level `_synthesize_one(item, *, backend, prompt_template, sources_out, chunk_max, write_lock) -> dict` | The pure per-source worker (see 2.3) |
| `llmwiki/synth/pipeline.py` | `synthesize_new_sessions(..., concurrency: int | None = None)`; loop body replaced by executor + `as_completed` drain (see 2.4) | Orchestration, all shared mutation, all printing |
| `llmwiki/synth/reporting.py` | new `print_synth_run_start(*, total, backend_name, concurrency)` | The start-of-run line and the empty-queue line |
| `llmwiki/synth/claude_cli.py` | `threading.Lock` guarding `_run_tokens` / `_run_cost_usd` / `_run_has_usage` in the record, `reset_usage`, and `take_usage` paths | Correct token/cost totals under concurrency |
| `llmwiki/synth/base.py` | docstring on `BaseSynthesizer.synthesize_source_page` | State the contract: may be called concurrently; implementations must be thread-safe |
| `llmwiki/cli.py` | `--concurrency N` in `_add_synth_arguments`; pass `concurrency=` at both `synthesize_new_sessions` call sites | Per-run override for `synth` and the deprecated `synthesize` alias |
| `llmwiki/pipeline.py` | no signature change | `all --with-synth` inherits config/default (see 2.7) |

### 2.3 The worker contract

`_synthesize_one` receives one entry from `new_items` plus run-wide read-only inputs, and returns a plain result record:

| Field | Meaning |
| --- | --- |
| `rel`, `mtime`, `project`, `is_doc`, `meta`, `slug` | Echoed back so the orchestrator can update state and tally producers without re-deriving anything |
| `written` | List of page names successfully written (one per chunk; several for a chunked doc) |
| `protected` | Count of chunks where a placeholder page was withheld to preserve a real page |
| `error` | `None`, or the exception's message |

Inside the worker: chunk the body (docs only), call `backend.synthesize_source_page` per chunk, build the page, then perform the guarded write. It catches `Exception` and returns it in `error` rather than raising, so one bad source can never tear down the executor drain.

**Guarded write.** A single module-level `threading.Lock` serializes the *read-existing → decide → write* sequence for a page: `_build_source_page(..., existing_page_path=out_path)` reads the target to preserve maintainer-curated tags (#351), and the stub guard reads it again to decide whether to withhold a placeholder. Two sources in one batch can derive the same target filename (same project, same date, same normalized slug), and an unguarded read-modify-write there could produce a torn page. The lock is held only for that cheap file I/O — never across the backend call — so it costs nothing against a multi-second LLM wait.

### 2.4 Orchestration

```
print_synth_run_start(total=len(new_items), backend_name=..., concurrency=...)   # before any work
if not new_items: → skip the executor entirely

with ThreadPoolExecutor(max_workers=concurrency) as pool:
    futures = {pool.submit(_synthesize_one, it, ...): it for it in new_items}
    for done, future in enumerate(as_completed(futures), start=1):
        result = future.result()
        # --- main thread only, from here down ---
        print each written page as  "  [done/total] synthesized: <project> → <name>"
        summary["protected"] += result["protected"]
        if result["error"]:  summary["errors"].append(...); summary["skipped"] += 1
                             print "  [done/total] error: <slug>: <msg>"
        else:                state[rel] = mtime; _save_state(...); _update_unified_state(_drop_pending, ...)
                             summary["synthesized"] += 1; producers[key] += 1
```

Because every line above the executor and every line inside the drain runs on one thread, `state`, `summary`, `producers`, and `sys.stdout` need no locks at all.

Everything after the drain — the single `_append_log` entry, the final `_save_state`, `refresh_synth_pending`, the gated `_rebuild_index`, and `take_usage()` — is unchanged and still runs exactly once, after all pages. The candidate harvest lives in the *callers*, after `synthesize_new_sessions` returns, so "harvest only after all sources" holds with no change.

**`concurrency == 1`** takes the same code path with a single worker; `as_completed` over a one-worker pool preserves submission order, so a sequential run's output ordering is unchanged apart from the new counter prefix.

### 2.5 Output contract

| Situation | Line |
| --- | --- |
| Start of a real run | `Synthesizing 11 source(s) with ClaudeCLISynthesizer (2 at a time)` |
| Start, empty queue | `Nothing to synthesize — every source is already up to date.` |
| Page written | `  [3/11] synthesized: <project> → <name>` |
| Placeholder withheld | `  [3/11] protected: <project> → <name> (kept real page; stub not written)` |
| Source failed | `  [3/11] error: <slug>: <message>` |

The position counts **completed sources**, and the total is the number of sources in the queue — so a chunked doc's part-pages all carry the same position, and the final completion's position always equals the announced total.

Two ordering notes:

- The dedup `skipped: … (real source page already claims this source…)` lines are emitted while the queue is being built, so they precede the start line. That is correct: FR1 requires the start line before any **result** line, and the count it announces already excludes those sources.
- `--dry-run` keeps its own existing `[dry-run] Would synthesize N …` line and returns before the start line. `--estimate` and `--check` return in the CLI long before reaching this function.

**Behavior change worth naming:** today a chunked doc prints each part the moment it is written; now all of a source's lines print together when that source completes. One source becomes one atomic progress unit, which is what makes the `[k/N]` counter meaningful.

### 2.6 Interrupt handling

`ThreadPoolExecutor.__exit__` calls `shutdown(wait=True)`, so a bare Ctrl-C would block until every in-flight page finished, with no explanation — worse than today, where Ctrl-C stops after the current page. The drain therefore catches `KeyboardInterrupt`, cancels not-yet-started futures (`shutdown(wait=False, cancel_futures=True)`), prints how many in-flight pages it is waiting on, and re-raises after they land. Sources that completed before the interrupt already have their state saved, so a re-run picks up exactly the remainder (FR5).

### 2.7 Scope boundary: `all --with-synth`

`llmwiki all --with-synth` gets the start-of-run line and parallelism automatically (both live inside `synthesize_new_sessions`), but **no new `--synth-concurrency` mirror flag** is added to the `all` parser. The saved `synthesis.concurrency` preference exists precisely for non-interactive and scheduled runs, which is what `all` serves; adding a second flag would mean two names for one number and a wider CLI surface for no capability the operator lacks. `--synth-force` mirrors `--force` today, so this is a deliberate departure from that precedent, not an oversight.

### 2.8 Documentation

- `docs/reference/cli.md` — a `--concurrency N` row in the `synth` flag table, plus a sentence in the `synth` narrative describing the start line and the `[k/N]` counter.
- `docs/configuration-reference.md` — a `synthesis` / `concurrency` row alongside `claude_timeout`.
- `CHANGELOG.md` — entry under `## [Unreleased]`.

---

## 3. Impact and Risk Analysis

### System Dependencies

- **`llmwiki/state_store.py`** — `update_state` already serializes writes with an `fcntl.flock` and `_save_state` upserts only the keys it is handed, so the state *file* is already safe. Only the in-memory dict was ever at risk, and the orchestrator-owns-mutation design removes that. No change needed here.
- **Backends** — `OllamaSynthesizer` sets instance attributes only in `__init__` and is already safe. `DummySynthesizer` is stateless. `ClaudeCLISynthesizer` is the one that needs the lock.
- **Callers** — `cli.py::cmd_synthesize` (×2 call sites) and `pipeline.py::run_pipeline`. Their post-run reporting (`Scanned … new … synthesized … skipped`, `print_synth_run_summary`, `run_harvest`) reads the same summary dict and is unchanged.
- **`llmwiki add`** — passes `only_paths`, usually a single source, so it sees no practical change.

### Potential Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| **Lost token/cost totals.** `self._run_tokens += tokens` is a read-modify-write across bytecodes; two threads can drop an update and silently under-report spend. | Instance `threading.Lock` around the accumulate/reset/take paths in `claude_cli.py`, plus a test that hammers the accumulator from many threads and asserts an exact total. |
| **Torn page on colliding target paths.** Two sources in one batch can derive the same filename. | The guarded-write lock in §2.3 makes read → decide → write atomic. |
| **Existing tests assert exact stdout.** The `[k/N]` prefix changes every per-page line. | Expected churn: audit the synth test modules and update assertions. Tests that assert *ordering* of parallel output must be rewritten to assert on sets, not sequences. |
| **Provider rate limits / machine load.** More concurrent calls means more chance of throttling, surfacing as page errors. | Default is 2 — the most conservative real parallelism. The ceiling is 16. Failures remain isolated per source and are reported, never silent. |
| **A backend that is not thread-safe** (today's, or one added later). | The ABC docstring states the contract explicitly, and `concurrency: 1` is a documented escape hatch that restores exact sequential behavior. |
| **Ctrl-C appears to hang.** | §2.6 — cancel pending, report in-flight, re-raise. |
| **Deadlock.** | Only two locks exist, they are never held simultaneously, and neither is ever held across a backend call. |
| **Reduced determinism makes failures harder to reproduce.** | Every error still carries its source slug, and `--concurrency 1` reproduces a run deterministically for debugging. |

---

## 4. Testing Strategy

New module `tests/test_synth_parallel.py`, plus additions to `tests/test_synth_run_summary.py` for the start line. All tests use `DummySynthesizer` or purpose-built fakes against a `tmp_path` vault — no live vault, no real LLM call.

**Unit — configuration resolution**
- Default with no config; a valid value; a missing key → default with **no** warning; `0` / `-1` / `"two"` / `2.5` → default plus a warning; a value above the ceiling → clamped plus a warning.

**Unit — CLI**
- `--concurrency 0` and a non-integer exit `2` with a message naming the range.
- Precedence: flag beats config; config beats default; default is 2. Asserted by monkeypatching `synthesize_new_sessions` and capturing the `concurrency` it receives.

**Behavioral — parallelism actually happens** (deterministic, no sleeps)
- A fake backend whose `synthesize_source_page` waits on a `threading.Barrier(2)` with a short timeout. At `concurrency=2` the barrier releases and the run succeeds; at `concurrency=1` it times out — proving the calls genuinely overlap rather than asserting on wall-clock timing.
- A fake that records concurrent entries/exits: assert peak in-flight is `> 1` at 4 and exactly `1` at 1.

**Equivalence — the core FR2/FR5 guarantee**
- Run the same fixture corpus at `concurrency=1` and `concurrency=4`, then assert identical page paths, identical page contents, identical `summary` counters (`synthesized`, `skipped`, `protected`, `new_files`, `total_scanned`), identical producers breakdown in the log entry, and identical resulting synth state.

**Behavioral — reporting**
- Start line precedes every `synthesized:` line and reports the queue size, backend name, and concurrency.
- Count excludes dedup-skipped sources.
- Empty queue prints the nothing-to-do line and no start count.
- `--dry-run` still prints only its own line.
- Every result line carries `[k/N]`; the final completion's `k` equals `N`; error lines carry a position too. Assertions are order-independent.

**Behavioral — correctness invariants (FR5)**
- One source's backend raises: the rest complete, the error is recorded, `skipped` increments, and the failed source's key is **absent** from the synth state → a re-run retries exactly it.
- Stub protection under concurrency: an existing real page plus a placeholder-producing backend leaves the real page byte-identical and increments `protected`.
- `_append_log` fires exactly once per run, and `_rebuild_index` is still gated on `synthesized > 0`.

**Thread-safety**
- `ClaudeCLISynthesizer` usage accumulation from many threads yields the exact expected token and cost totals.

**Regression sweep**
- `ruff check llmwiki tests scripts` and the full `python3 -m pytest tests/ -q` — with attention to the existing `test_synth_*` modules whose stdout assertions the counter prefix changes.
