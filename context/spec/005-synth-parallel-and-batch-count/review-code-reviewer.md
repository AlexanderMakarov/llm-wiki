# Code review — `feat/118-synth-parallel`

Scope reviewed: `git diff origin/main...HEAD` (15 files, +2440/−90). Source under review: `llmwiki/synth/pipeline.py`, `llmwiki/synth/claude_cli.py`, `llmwiki/synth/base.py`, `llmwiki/synth/reporting.py`, `llmwiki/cli.py`; plus `CHANGELOG.md`, `docs/reference/cli.md`, `docs/configuration-reference.md`, `context/spec/005-synth-parallel-and-batch-count/*`, and the three test files. Reviewed as written — the test suite was not executed. `ruff check llmwiki tests scripts` was run and passes.

**Verdict: approve with follow-ups.** No critical (90–100) issues. The concurrency design is sound: every shared mutation (state, summary counters, producer tallies, stdout) stays in the draining thread, `write_lock` correctly wraps only the read-existing → decide → write sequence and leaves the backend call outside it, and all three backends (`DummySynthesizer`, `OllamaSynthesizer`, `ClaudeCLISynthesizer`) hold no unguarded cross-call state — `ClaudeCLISynthesizer._resolved()` resolves through `llmwiki/claude_path.py`, which has no cache or mutable global. The usage-counter lock, the bounded worker count (1–16), and the strict CLI validation against a tolerant config path all check out. No security issues: no `shell=True`, no new runtime dependency, no untrusted input reaching a subprocess argv, and thread/subprocess fan-out is capped.

## Important (80–89)

### 1. Ctrl-C discards the results of pages that still write to disk — they are re-synthesized (and re-billed) on the next run. Confidence: 82

`llmwiki/synth/pipeline.py:1501-1512`

```python
            except KeyboardInterrupt:
                pool.shutdown(wait=False, cancel_futures=True)
                in_flight = sum(1 for f in futures if f.running())
                print(
                    f"\nInterrupted after {completed}/{total} source(s) — "
                    f"waiting for {in_flight} page(s) already in flight."
                )
                raise
```

`shutdown(wait=False, cancel_futures=True)` cancels only *queued* futures. The `raise` then leaves the `with ThreadPoolExecutor(...)` block, whose `__exit__` calls `shutdown(wait=True)` and joins the workers — so the in-flight `_synthesize_one` calls run to completion and **do** write their `wiki/sources/**.md` pages. But their futures are never drained: `state[rel]` is not set, `_save_state` is not called for them, `summary["synthesized"]` is not incremented, and no `synthesized:` line is printed.

Consequences on the next run: `it["rel"] not in state`, and the dedup guard does not skip them either (a real page *at* the derived target sets `derived_has_real=True`, which is explicitly the overwrite path at `pipeline.py:1389-1396`), so up to `concurrency` sources are synthesized a second time — one extra paid `claude -p` call each. The printed message compounds this: it tells the operator the exit is "waiting for" those pages, which reads as "they will land", when in fact their work is thrown away as far as the run's bookkeeping is concerned. Sequential runs did not have this class of loss, because a Ctrl-C interrupted the single backend call rather than letting a completed page go unrecorded.

Suggested fix — drain what actually finished before re-raising:

```python
            except KeyboardInterrupt:
                pool.shutdown(wait=False, cancel_futures=True)
                in_flight = sum(1 for f in futures if f.running())
                print(
                    f"\nInterrupted after {completed}/{total} source(s) — "
                    f"waiting for {in_flight} page(s) already in flight."
                )
                # Pages that finish during the executor's join wrote their
                # file; record them so the resume does not re-bill them.
                for f in futures:
                    if f.cancelled():
                        continue
                    try:
                        res = f.result()
                    except (Exception, CancelledError):
                        continue
                    if res["error"] is None and res["rel"] not in state:
                        state[str(res["rel"])] = res["mtime"]
                _save_state(state, state_file)
                raise
```

(Any equivalent shape works — recording state inside `_synthesize_one` under `write_lock` would also close it. The point is that a written page must not be invisible to the resume.)

### 2. New fixture docstring documents behaviour this same PR removed. Confidence: 85

`tests/test_synth_parallel_acceptance.py:186-200`

The autouse `_isolate_synth_log` fixture's docstring states:

> ``cmd_synthesize`` never forwards a vault-scoped ``log_path`` into ``synthesize_new_sessions`` … a pre-existing gap outside #118's scope, not something this suite is testing. Left unpatched, a CLI-driven test with ``--vault <tmp>`` would still append its log entry to the pipeline's module-level ``WIKI_LOG`` fallback, which lives inside this repository's own working tree.

That is no longer true after this PR. `cmd_synthesize` maps `--vault` onto `wiki_sources_dir` (`llmwiki/cli.py:1142-1144`), and `pipeline.py:1526` now resolves the log to `log_path or (sources_out.parent / "log.md")` — so a `--vault <tmp>` run writes its entry to `<tmp>/wiki/log.md`, never to `WIKI_LOG`. The PR's own `CHANGELOG.md` "Fixed" entry and `tests/test_synth_parallel.py:633-663` (`test_the_log_entry_lands_in_the_vault_that_was_synthesized`) both assert the opposite of what this docstring claims.

The fixture itself is harmless (a now-redundant safety net), but the docstring will mislead the next reader into believing an already-closed gap is still open — and it describes it as out of scope for the very issue that closed it. Fix: either delete the fixture, or rewrite the docstring to say it is a belt-and-braces guard against the module-level fallback for any test that does *not* pass a vault.

### 3. CONTRIBUTING rule 1 — a bug fix is bundled with the feature. Confidence: 80

`llmwiki/synth/pipeline.py:1519-1527`, `CHANGELOG.md` (the "Fixed" entry)

CONTRIBUTING's first non-negotiable is "One concern per PR. No mixing a bug fix with a feature." This branch ships the #118 feature (parallel synth + batch-count announcement) *and* an independent correctness fix — deriving the `wiki/log.md` target from `wiki_sources_dir` instead of the import-time module constant, so a vault-scoped run stops writing its history into whichever wiki sits beside the installed package. The fix has its own `CHANGELOG.md` "Fixed" bullet, its own two tests (`test_synth_parallel.py:633-684`), and is not required by the parallel work — it is a clean, separable concern.

The change itself is correct and I would not ask for it to be reverted; flagging it so it is a deliberate, stated exception in the PR body (per the rule's "state it explicitly" escape) rather than an unremarked mix. If the maintainer prefers strictness, split it into its own `fix:` PR — it is ~10 lines of source plus two tests.

## Below the reporting threshold (noted, not blocking)

- `--concurrency` is validated (`llmwiki/cli.py:1058-1068`) before the `--candidates-only` early return at `cli.py:1076`, so `llmwiki synth --candidates-only --concurrency 99` exits 2 on a flag that path never uses. Confidence ~70.
- `print_synth_run_start`'s empty-queue text, "Nothing to synthesize — every source is already up to date.", is inaccurate when the queue is empty because sources were dedup-skipped or filtered as ineligible rather than up to date. Knowingly worded that way per the CHANGELOG. Confidence ~70.
- A `KeyboardInterrupt` arriving during the `pool.submit` list comprehension (`pipeline.py:1443-1455`) is not caught, so the executor's `__exit__` joins silently with no "interrupted" message. Narrow window. Confidence ~65.
- Two sources in one batch that derive the same target filename now preserve maintainer-curated tags nondeterministically (whichever thread reaches `_build_source_page` first). Pre-existing collision case; concurrency only changes which one wins. Confidence ~60.
- `_TrackingBackend`'s `peak` assertions (`test_synth_parallel.py:456-473`, acceptance `:236-258`) rest on a 20–30 ms hold rather than a barrier, unlike the deterministic `_BarrierBackend` tests beside them. Generous margin, but the only wall-clock-shaped assertions in the suite. Confidence ~65.

## Verified clean

- Thread-safety of the shared `backend` instance across all three implementations; `BaseSynthesizer.synthesize_source_page`'s new contract docstring matches what the pipeline actually does.
- `write_lock` scope: covers `_build_source_page`'s read of the existing page, the `_is_stub_page` guard's re-read, and `write_text` as one critical section; excludes the backend call. `out_dir.mkdir(parents=True, exist_ok=True)` is safe unlocked.
- Parity with the sequential path for stub protection, per-source state updates, `summary` counters, the single log entry with producer breakdown, and the `--force` / dedup-guard decisions.
- `resolve_synth_concurrency` handles the `bool`-is-an-`int` trap, non-int, sub-1, missing key, and over-cap clamping; the explicit-argument path is routed through the same helper so a library caller cannot inject an out-of-range worker count.
- `ClaudeCLISynthesizer` usage accounting is guarded on all three mutation sites (`reset_usage`, `take_usage`, the `+=` in `synthesize_source_page`) with the lock never held across `subprocess.run`.
- Docs: `--concurrency` has its row in `docs/reference/cli.md` and `synthesis.concurrency` in `docs/configuration-reference.md`, satisfying the CI CLI-coverage check; `CHANGELOG.md` has an `## [Unreleased]` entry; `context/` is updated, satisfying the AWOS gate.
- Privacy: no absolute home paths, usernames, hostnames, or real session data anywhere in the diff. No hard-wrapped markdown prose in the new `.md` files. No new runtime dependencies.
