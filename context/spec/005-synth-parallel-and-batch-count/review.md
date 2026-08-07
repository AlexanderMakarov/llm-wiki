# Maintainer checklist review — #118 Synth batch count and parallel page synthesis

- **Branch:** `feat/118-synth-parallel` (worktree `.claude/worktrees/feat-118-synth-parallel`)
- **Scope reviewed:** `git diff origin/main...HEAD` — commits `a940bad` (spec) and `6e21f4d` (implementation). No PR open yet; this is the pre-push gate.
- **Issue:** #118 · **Approved design:** [`technical-considerations.md`](./technical-considerations.md) · **Contract:** [`functional-spec.md`](./functional-spec.md)
- **Checklist:** `docs/maintainers/REVIEW_CHECKLIST.md`, all sections
- **Date:** 2026-08-07
- **Verdict:** **changes-requested** — 1 blocker, 2 important, 9 nits

## Summary

The design is the right one and it is faithfully implemented. Making `_synthesize_one` pure with respect to run state, and keeping every shared mutation (`state`, `summary`, `producers`, stdout) inside the single-threaded `as_completed` drain, removes the concurrency hazard structurally rather than by locking — which is the hard part of this change and it is done correctly. I found no data race in the delivered code: the two locks that exist (`ClaudeCLISynthesizer._usage_lock`, the per-run `write_lock`) are correctly scoped, are never held across a backend call, are never held simultaneously, and I verified by reading that `DummySynthesizer` is stateless and `OllamaSynthesizer` mutates instance attributes only in `__init__`. The test suite is unusually good for a concurrency change: the overlap proofs are barrier-based rather than sleep-based, and the flow log records that the thread-safety test was mutation-checked against a deliberately-neutralised lock (a real risk on CPython 3.12, where a straight-line `+=` never yields).

One blocker: the drain handles `KeyboardInterrupt` specially — correctly, and for exactly the right reason — but every *other* escape from the drain still falls through `ThreadPoolExecutor.__exit__`, whose `shutdown(wait=True)` runs the entire remaining queue before the traceback surfaces. On a 50-source catch-up that is 50 backend calls and real spend, silently, after a failure. The same reasoning §2.6 applied to Ctrl-C applies here; the fix is ~4 lines.

Two important items are documentation truth: an acceptance-suite fixture docstring asserts the log-path defect is still open (this branch closed it), and both spec documents still describe a config warning on a *missing* key that the code deliberately does not emit.

The scope-added vault log-path fix is correct and well-targeted. `sources_out.parent` resolves to `<vault>/wiki` for all four callers (`cli.py::cmd_synthesize`, `cli.py::cmd_add`, `pipeline.py::run_pipeline`, `queue_ops.py`), and with no vault `WIKI_SOURCES.parent / "log.md"` is byte-identical to `WIKI_LOG`, so default behaviour is provably unchanged. Both regression directions are covered.

---

## Findings

### Blockers

**1. Only `KeyboardInterrupt` stops the batch — any other exception silently drains the whole queue first**

`llmwiki/synth/pipeline.py:1454–1512`. The drain is wrapped in `try: … except KeyboardInterrupt:`, which calls `pool.shutdown(wait=False, cancel_futures=True)` before re-raising. Nothing else is caught. Any other exception escaping the `for future in as_completed(futures):` loop propagates out of the `with ThreadPoolExecutor(...)` block, and `__exit__` calls `shutdown(wait=True)` with `cancel_futures=False`.

I verified the consequence against the stdlib rather than assuming it — `/usr/lib/python3.12/concurrent/futures/thread.py::_worker` pulls work items until the queue is *empty* and only then checks `_shutdown`:

```python
work_item = work_queue.get(block=True)
if work_item is not None:
    work_item.run()
    continue
```

So a plain `shutdown(wait=True)` executes every queued page. A failure on completion 2 of 50 runs the other 48 backend calls — minutes of wall clock and real provider spend — with nothing printed, and then raises. Sequentially, the same failure aborted immediately after the current page. This is a behavioural regression on the exception path, and it is the precise failure mode §2.6 was written to prevent for Ctrl-C.

Two reachable routes into it:

- **The worker's prologue is outside its `try`** — `llmwiki/synth/pipeline.py:1124–1147`. `_normalise_slug(...)`, `synth_page_filename(meta, p.stem)` and `_chunk_markdown(body, chunk_max)` all run before `try:`. Anything they raise is stored on the future and re-raised by `future.result()` in the drain. (The old sequential loop had the same lines outside its `try`, so *what* raises is unchanged — only the consequence is worse.)
- **The drain itself** — `_save_state(state, state_file)` (l. 1497, `OSError` on a full or read-only vault), `detect_agent_label(res["meta"])` (l. 1510), or a `print` onto a closed pipe.

Fix (both halves):

1. Move the worker prologue inside `_synthesize_one`'s `try` so those failures become ordinary `error` records instead of escaping. `result` is built before the prologue anyway, so the record already exists to attach the error to — only `slug` needs a safe default first.
2. Widen the drain's handler so any escape shuts the pool down the same way Ctrl-C does:

```python
except BaseException:
    pool.shutdown(wait=False, cancel_futures=True)
    raise
```

placed *after* the `except KeyboardInterrupt:` clause (which keeps its operator-facing message). A regression test can assert that a drain-side failure leaves the untouched sources absent from the synth state and the backend's call count well below the queue size.

### Important

**2. The acceptance suite's autouse fixture documents the defect this branch fixed as still open**

`tests/test_synth_parallel_acceptance.py:186–200`. `_isolate_synth_log`'s docstring states:

> ``cmd_synthesize`` never forwards a vault-scoped ``log_path`` into ``synthesize_new_sessions`` … a pre-existing gap outside #118's scope, not something this suite is testing.

That is no longer true — commit `6e21f4d` closed exactly that gap, and `CHANGELOG.md` has a `### Fixed` entry saying so. The fixture is also now inert for the in-process tests it names: `synthesize_new_sessions` always hands `_append_log` a non-`None` `log_path`, so `synth_pipeline.WIKI_LOG` is never consulted on that path. Checklist §Docs, "docstrings match the code". Either delete the fixture, or keep it as a belt-and-braces guard and rewrite the docstring to say what it actually guards now — a future unscoped run touching the checked-out repo's `wiki/log.md`. Leaving it as-is will tell the next maintainer a fixed bug is still open.

**3. Both spec documents still describe a warning on a missing `synthesis.concurrency` key that the code deliberately does not emit**

`technical-considerations.md` §2.1 says "A **missing**, non-integer, or out-of-range value falls back to the default and emits a `logging` warning naming the accepted range". `tasks.md` Slice 2 repeats it: "missing, non-integer, `< 1`, or boolean values fall back to the default and log a warning". The delivered `resolve_synth_concurrency` (`llmwiki/synth/pipeline.py:243–248`) returns the default silently when the key is absent, and only warns for present-but-unusable values.

The delivered behaviour is the better one and the flow log records it as a considered deviation ("Warning on absence would print a stderr WARNING for every operator who never touched the setting" — correct: llmwiki calls no `logging.basicConfig`, so `logging.lastResort` puts every WARNING on the operator's stderr). But the approved design was never amended to match, so the two spec files now describe code that does not exist. `docs/configuration-reference.md` already states it correctly ("a missing key is silent"). Amend §2.1 and the Slice 2 task text; this is the same drift class that was raised on the #113 review.

### Nits

**4. A library-supplied `concurrency` produces a warning that blames `config.json`** — `llmwiki/synth/pipeline.py:1264` normalises an explicit argument by wrapping it: `resolve_synth_concurrency({"synthesis": {"concurrency": concurrency}})`. Routing through one helper is the right call, but `synthesize_new_sessions(concurrency=0)` from the MCP server or a script then logs `Invalid synthesis.concurrency 0 — must be an integer in 1..16`, naming a config key the caller never set. The CLI is unaffected (it rejects first). Consider a `source: str = "synthesis.concurrency"` parameter on the helper so the message can say `concurrency argument` instead.

**5. `print_synth_run_start`'s optional-`concurrency` branch is unreachable and untested** — `llmwiki/synth/reporting.py:49–71`. The parameter was left optional so Slice 1 could ship before Slice 4 filled in the suffix; that reason expired when Slice 4 landed. The sole production caller (`pipeline.py:1426`) always passes it, and no test exercises the suffix-less form, so the documented "Omitted when the caller leaves it unset" path is dead surface. Checklist §Code quality, "no dead code". Make it required, or add the one-line test.

**6. `--concurrency` is validated in the command body, not at parse time** — the approved design (§2.1) says "`--concurrency` is validated at parse time and a bad value exits `2`". Delivered, argparse takes only `type=int` and the range check is in `cmd_synthesize` (`llmwiki/cli.py:1058–1068`). Both exit `2` with a range message so the user-facing contract holds, but the error is not formatted like argparse's other parse errors, and it now also fires on `synth --check --concurrency 0`, which never reaches the executor. Worth either matching the spec (an argparse `type=` callable raising `ArgumentTypeError`) or amending §2.1 to describe what shipped.

**7. Within one source, `protected:` lines now print after all of its `synthesized:` lines** — `llmwiki/synth/pipeline.py:1470–1481` drains `res["written"]` fully before `res["protected_pages"]`. Sequentially the two interleaved in chunk order. Only observable on a chunked multi-part doc that protects some parts and writes others, and it is harmless, but it makes the tasks.md claim that the worker is "byte-for-byte what the loop does today" slightly stronger than the code. Either reorder into one merged per-chunk list, or note the ordering change alongside the one §2.5 already names.

**8. Three near-identical copies of the test corpus helpers** — `_DOC`, `_CLAIMING_PAGE`, `_mk_vault`, `_seed_docs`, `_claim_source` are duplicated across `tests/test_synth_parallel.py`, `tests/test_synth_parallel_acceptance.py` and `tests/test_synth_run_summary.py`, and `_BarrierBackend` / `_TrackingBackend` / `_FlakyBackend` exist in two of them with slightly different base classes and defaults. A shared `tests/helpers/synth_corpus.py` (or a conftest fixture) would cut roughly 150 duplicated lines and stop the three copies drifting.

**9. `_TrackingBackend`'s overlap assertion is timing-widened, not structurally guaranteed** — `tests/test_synth_parallel.py:458,469` holds each call for 20 ms so that `parallel.peak > 1` at `concurrency=4`. Very likely, but not deterministic the way the barrier tests are. Low risk and the barrier pair already carries the load-bearing proof; noting only so nobody later "strengthens" this into the primary evidence.

**10. `llmwiki add` gains an unannounced start line** — `add` routes through `synthesize_new_sessions`, so after its own `Synthesizing with backend: <name>` (`llmwiki/cli.py:1343`) it now also prints `Synthesizing 1 source(s) with <backend> (2 at a time)`, or `Nothing to synthesize — every source is already up to date.` when the doc was already synthesized. Consistent with FR's "wherever synth runs as part of a larger pipeline", but the doubled line reads oddly and `docs/reference/cli.md`'s `add` section does not mention it. Cosmetic.

**11. Commit shape: the `fix:` concern rides inside the `feat:` commit** — the scope addition itself was an explicit maintainer decision at the smoke gate and is not reviewed as a violation, but `6e21f4d` mixes it into the feature commit while `CHANGELOG.md` correctly splits it into `### Added` and `### Fixed`. CONTRIBUTING's "atomic commits — each commit tells a clear story" would be better served by splitting it out before push, so the two changelog entries trace to two commits. Cheap now, impossible after merge.

**12. The one subprocess-level CLI test cannot catch a regression of the log-path fix** — `tests/test_synth_parallel_acceptance.py:326` is the only `_run_cli(...)` invocation, and it runs against an *empty* vault, so it never writes a log entry (the autouse monkeypatch does not reach a subprocess). The fix is properly covered in-process at `tests/test_synth_parallel.py:633`, so coverage is fine; but if you want the end-to-end guard, point one non-empty `_run_cli` run at a tmp vault and assert the repo's own `wiki/log.md` is unchanged.

---

## Checklist application

### Meta

- **Linked issue** — #118, with the full approved spec set under `context/spec/005-…/`. ✅ The PR body must carry `Closes #118` and explicitly flag the log-path fix as a maintainer-approved scope addition.
- **One concern per PR** — two concerns (parallel synthesis; vault-scoped log path). Maintainer-approved at the smoke gate and recorded in `flow-log.md`; not reported as a violation. See nit 11 on commit shape.
- **Conventional-commit titles** — `feat:` and `docs:`. ✅
- **CHANGELOG entry** — both an `### Added` and a `### Fixed` entry under `## [Unreleased]`, each referencing #118. ✅
- **Tests added or updated** — extensive; the log fix has a regression test in both directions (vault-scoped wins, explicit `log_path` still wins), and the flow log documents that it was mutation-checked. ✅
- **CI is green** — not run in this review per instructions. Caller reports 3786 passed / 46 skipped and `ruff check llmwiki tests scripts` clean.
- **AWOS context** — `llmwiki/`, `tests/` and `docs/reference/` all changed, and `context/spec/005-…/` changed alongside. ✅

### Layer boundaries

- **Layer-appropriate** — the diff sits entirely in the synth pipeline, its reporting helper, one backend, the CLI parser, and three docs files. `build.py`, `convert.py`, `render/`, adapters and CSS are untouched. ✅
- **No new runtime deps** — `threading` and `concurrent.futures` are stdlib. ✅
- **Layer-0 stays stdlib-only** — not touched. ✅

### Security + privacy

- **No real session data** — every fixture is synthetic (`_DOC`, `_CLAIMING_PAGE`, `doc00…doc07`). ✅
- **Redaction** — untouched, no converter or regex change. n/a
- **XSS** — no HTML is rendered by this diff. n/a
- **No network calls** — the change fans out existing backend calls; it introduces none. The `MAX_SYNTH_CONCURRENCY = 16` ceiling is a deliberate resource guard because the number bounds concurrent `claude -p` *subprocesses*, and it is enforced on both the config path (clamp + warn) and the CLI path (reject). Good. ✅
- **Localhost binding** — no server code. n/a
- **Telemetry** — none. ✅
- **Privacy grep** — the only personal-looking string in the diff is the fork owner's GitHub handle in `context/spec/005-…/*.md`, matching specs 001–004. No home paths, no OS usernames, no keys, no vault roots. ✅

### Code quality

- **Docstrings** — `resolve_synth_concurrency`, `print_synth_run_start` and `_synthesize_one` all carry substantive docstrings; `_synthesize_one`'s states the shared-state and lock contracts explicitly, and `BaseSynthesizer.synthesize_source_page` now documents the thread-safety contract for future backends. ✅
- **Comments answer "why"** — the write-lock rationale, the read-modify-write hazard on the usage counters, and `bool` being an `int` subclass are all explained where a reader would otherwise stall. ✅
- **Error handling** — config tolerant / CLI strict is a good split and matches `resolve_backend`'s precedent; the worker converts `Exception` into an `error` record so one bad source cannot end the run. The gap is blocker 1.
- **Type hints** — present and consistent with neighbours. ✅
- **Dead code** — nit 5.

### Tests

- **Happy path + edges** — resolution covers `0`, `-1`, `"two"`, `2.5`, `True`, missing, and `999`; behaviour covers empty queue, dedup-skipped sources, `--dry-run`, failure isolation with state absence, stub protection under `--force`, single `_append_log`, gated `_rebuild_index`, and a full sequential-vs-parallel equivalence run over 8 sources comparing page paths, page contents, all five counters, the producer breakdown and the resulting state. ✅
- **Test names describe behaviour** — consistently, e.g. `test_one_failure_leaves_rest_complete_and_resumes_only_it`. ✅
- **Regression tests lock in the fix** — yes, both directions for the log path. ✅
- **No reliance on the real filesystem outside tmp_path** — all vaults are under `tmp_path`. The one subprocess test runs with `cwd=REPO_ROOT` but is `--vault`-scoped and writes nothing to the repo; see nit 12. ✅
- **Local pytest** — not re-run here per instructions.

### Docs

- **README** — not updated; no new top-level surface. Acceptable.
- **CHANGELOG** — ✅
- **docs/** — `docs/reference/cli.md` gains the `--concurrency` flag row plus a narrative paragraph on the start line and the `[k/N]` counter; `docs/configuration-reference.md` gains the `synthesis` / `concurrency` row. Both accurate against the code, including the "missing key is silent" detail the spec files get wrong. ✅
- **Docstrings match the code** — important 2 and nit 5.

### Build + runtime smoke

Not run, per the review instructions. No `build.py` / `render/` change, so generated site output is unaffected by construction. `flow-log.md` records live CLI evidence on a scratch vault covering the start line, out-of-order completions, flag-beats-config precedence, `--concurrency 1`, range rejection at both bounds, the empty-queue line, stub protection under `--force`, and harvest ordering.

---

## Concurrency-specific audit (requested focus)

| Concern | Finding |
|---|---|
| Mutable state shared across threads | None. `state`, `summary`, `producers` and stdout are touched only inside the drain, which is single-threaded. Workers receive read-only run inputs plus their own `item` and return a fresh record. `new_items` entries are read, never mutated. |
| Lock scope — too wide | `write_lock` covers `_build_source_page` (one small read) + the stub-guard read + `write_text`. The backend call is outside it, which is the whole point. `_usage_lock` covers only the arithmetic, never `subprocess.run`. Both correct. |
| Lock scope — too narrow | `out_dir.mkdir(exist_ok=True)` and `p.stat()` sit outside the lock and are safe unguarded. The colliding-filename case §2.3 identifies is genuinely covered: the read → decide → write sequence is atomic, so the loser of a collision overwrites cleanly rather than tearing — the same last-writer-wins outcome the sequential loop had. |
| Ordering assumptions | `[k/N]` counts completions, not queue order, and is computed in the drain — correct. At `concurrency=1` `as_completed` over a single worker preserves submission order, so sequential output is unchanged apart from the prefix. The only ordering change beyond the documented one is nit 7. |
| Exception paths leaving state inconsistent | Worker failure is clean: `mtime` stays `None`, `error` is set, the drain `continue`s before touching `state`, so the source is retried on the next run — and `tests/test_synth_parallel.py` asserts exactly that key is absent. A partial write (chunk 3 fails after chunks 1–2 wrote) prints the written pages then the error and does *not* mark the source done, matching the old loop. The unhandled case is blocker 1. |
| Interrupt handling | Does what it claims for Ctrl-C: cancels queued futures, reports the in-flight count, re-raises, and lets `__exit__` wait for the running pages. Pages that finish *after* the interrupt have their files written but no state entry, so they are re-synthesized on the next run — a small, acceptable cost the spec effectively acknowledges. Everything else falls into blocker 1. |
| Backend thread-safety | `ClaudeCLISynthesizer` is now guarded on all three touch points (accumulate, `reset_usage`, `take_usage`) and `take_usage` correctly returns inside the lock. `_resolved()` is a pure lookup with no module-level cache. `OllamaSynthesizer` sets instance attributes only in `__init__` (l. 210–212). `DummySynthesizer` is stateless. Verified by reading, not assumed. ✅ |
| Deadlock | Two locks, never held simultaneously, neither held across a backend call. No cycle possible. ✅ |
