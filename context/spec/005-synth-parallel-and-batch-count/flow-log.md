# Flow log — 005-synth-parallel-and-batch-count (#118)

Memory of the `/implement-feature` run outside the context window. One entry per completed stage. Finalized at the commit-push stage — nothing is appended once the PR is open.

## fetch-ticket

- **Ticket:** GitHub Issue #118 — "synth: print pending file count at start; run page synthesis in parallel" (`enhancement`, `important`, state `OPEN`), https://github.com/AlexanderMakarov/llm-wiki/issues/118
- No comments, no attachments. Related: #113 (merged as PR #119) — this issue is its smoke-feedback follow-up; token/cost reporting stays on #113.
- **Next:** resume-detection.

## resume-detection

- Issue OPEN; no `context/spec/*` directory for #118; no branch matching `118`; only PR referencing 118 is #119 (which is #113's work, merged). Nothing to resume — full chain from workspace.
- **Next:** workspace.

## workspace

- **Branch:** `feat/118-synth-parallel` off `origin/main` @ `be38e40`
- **Worktree:** `.claude/worktrees/feat-118-synth-parallel`
- **Throwaway vault:** `<WT>/.worktree-vault`, worktree `config.json` points at it; `llmwiki init` seeded it. `setup.sh` run with `LLMWIKI_SKIP_AUTOMATION=1` (needed `bash ./setup.sh` — file is not executable in a fresh worktree).
- Primary checkout tree was clean at start.
- **Next:** specs.

## specs — functional spec

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/functional-spec.md` (`SPEC_NAME=005-synth-parallel-and-batch-count`)
- **Decisions taken with the user (AskUserQuestion):**
  - Default concurrency: **2 pages at a time** (user chose the conservative option over the recommended 4).
  - Override: **both** a per-run CLI option **and** a saved config preference; the CLI option wins.
  - Progress display: **completed/total counter prefixed on each per-page line**.
  - Local (Ollama) synthesizer gets the **same default** as the Claude CLI synthesizer — one number, one mental model.
- Spec carries FR1–FR6 (start-of-run count, parallel execution, override + validation, progress counter, unchanged results/failure semantics, discoverability) with 29 acceptance criteria.
- **Gate:** user approved ("lgtm"), 2026-08-06.
- **Next:** `/awos:tech`.

## specs — technical considerations

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/technical-considerations.md`
- **Design:** `ThreadPoolExecutor` (stdlib — no new dep) over a **pure** per-source worker `_synthesize_one`; the main thread drains `as_completed` and owns *every* shared mutation (`state` dict, `_save_state`, pending-drop, `summary`, `producers`, stdout). That structurally removes most locking.
- **Findings that drove the design (verified by reading, not assumed):**
  - `state_store.update_state` already serializes with `fcntl.flock` and `_save_state` upserts only passed keys → the state *file* was never the hazard, only the in-memory dict.
  - `ClaudeCLISynthesizer.synthesize_source_page` does `self._run_tokens += …` (read-modify-write) → needs an instance `threading.Lock`, else token/cost totals silently under-report.
  - `OllamaSynthesizer` mutates instance attrs only in `__init__`; `DummySynthesizer` is stateless → both already thread-safe.
  - Two sources in one batch can derive the same target filename → a module-level write lock makes `_build_source_page` (reads target for #351 tag preservation) → stub guard (reads target) → `write_text` atomic. Never held across a backend call.
- **Decisions taken without asking (flagged to the user at the gate):**
  - Config key `synthesis.concurrency` (default 2, ceiling `MAX_SYNTH_CONCURRENCY = 16`). Ceiling exists because the number bounds concurrent `claude -p` **subprocesses**.
  - Validation split: config values tolerant (warn + fall back, matching `resolve_backend`); CLI values strict (exit 2), because a silently-ignored typed flag is worse than a refusal.
  - **No `--synth-concurrency` mirror flag on `all`** — deliberate departure from the `--synth-force` precedent; the saved preference already serves non-interactive runs.
  - Ctrl-C: catch in the drain, `shutdown(wait=False, cancel_futures=True)`, report in-flight count, re-raise — otherwise `__exit__`'s `wait=True` looks like a hang.
  - Multi-part docs now print all their lines together on source completion (one source = one progress unit) instead of per part as written.
- **Known churn:** the `[k/N]` prefix changes every per-page stdout line, so existing `test_synth_*` stdout assertions need updating; ordering assertions must become order-independent.
- **Gate:** user approved ("lgtm"), 2026-08-07.
- **Next:** `/awos:tasks`.

## specs — tasks

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/tasks.md` — 6 slices, 25 tasks. Draft Approve loop suppressed per delivery-flow §10 (summary reported to chat, non-blocking).
- **Slice ordering rationale:** the risky threading slice lands last among implementation slices, after the setting it needs (Slice 2) and after the backends it calls are proven thread-safe (Slice 3), so Slice 4 never ships a known race. Slice 1 (count line) is independent of everything.
  1. Batch count at start of run (FR1 partial — count + backend)
  2. `synthesis.concurrency` + `--concurrency` + validation/precedence, still sequential (FR3)
  3. Backend thread-safety: `ClaudeCLISynthesizer` usage lock + `BaseSynthesizer` contract (FR5 prerequisite)
  4. Parallel execution: pure `_synthesize_one` worker, executor + `as_completed` drain, write lock, `[k/N]` counter, Ctrl-C handling, start-line concurrency, existing-test sweep (FR2, FR4, FR1 complete)
  5. Docs: `docs/reference/cli.md`, `docs/configuration-reference.md`, `CHANGELOG.md` (FR6)
  6. Feature Testing & Regression (`testing-expert`)
- **Agents:** implementation/verify → `general-purpose` (no Python specialist in this session's roster; the repo's `.claude/rules/contributing.md` auto-loads on `llmwiki/`/`tests/`/`scripts/`/`docs/` edits, so conventions still reach it). QA slice → project-local `testing-expert`. Recorded in the tasks.md Recommendations table.
- **Note on Slice 1 → Slice 4:** `print_synth_run_start` takes an optional `concurrency` arg it does not render until Slice 4, so the intermediate state never prints a number it isn't honoring.
- **Next:** commit specs, then `/awos:implement`.

## implement

- All 6 slices, 27/27 tasks complete. Production diff: 5 files, +303/−87 (inside the ≤500 target). Docs +5 lines across 3 files. Tests: `test_synth_parallel.py` (49) and `test_synth_parallel_acceptance.py` (20) added, `test_synth_run_summary.py` +155.
- **Interruption and recovery:** the Slice 4 implementation agent died mid-run on an API spend limit. It had completed tasks 1–5 (worker extraction, write lock, executor drain, Ctrl-C handling, start-line suffix) but not the existing-assertion sweep. Recovered in the main context: swept the two stale regexes in `test_synth_run_summary.py` (`_START_LINE` gained the ` (N at a time)` suffix, `_PAGE_LINE` the `[k/N]` prefix — those were the only two assertions in the whole suite affected), reviewed the drain and worker by hand, then wrote the nine parallel-execution tests.
- **Do not run two agents in one worktree.** Concurrent edits trip the repo's working-copy mutation guard mid-`pytest`, producing teardown ERRORs that name files the running agent never touched. Slices 1 and 3 were dispatched in parallel on disjoint files and still hit it. Everything after was serialized.
- **Tests were mutation-checked, not just run.** A naive threading stress test is vacuous on CPython 3.12 — the interpreter does not switch threads inside a straight-line `self._run_tokens += tokens`, so the unlocked accumulator produced exact totals every run and the test passed with the lock deleted. It needed a `_YieldingCounters` subclass exposing the counters as properties that read then yield the GIL. Likewise, forcing `ThreadPoolExecutor(max_workers=1)` was used to confirm the two overlap tests can actually fail; the QA agent ran 10 further perturbations, each reddening its intended tests before being reverted.
- **Deliberate deviation kept:** a *missing* `synthesis.concurrency` key falls back to the default with no warning (only present-but-unusable values warn), matching `resolve_backend`'s treatment of a missing `synthesis.backend`. Warning on absence would print a stderr WARNING for every operator who never touched the setting.
- **Next:** `/awos:verify`.

## verify

- Spec Status → `Completed` on both `functional-spec.md` and `technical-considerations.md`; all 24 acceptance criteria marked verified.
- Live CLI evidence on a scratch vault (deleted after): start line before results with backend and concurrency; out-of-order completion visible (`[1/4] a2` before `a1`) proving real overlap; flag 3 beating config 7; `--concurrency 1`; range rejection exiting 2 for both `0` and `99`; the empty-queue line after rewriting pages as non-stub; stub protection under `--force` leaving pages byte-identical; harvest running after all sources on a default `synth`. Gate: `ruff` clean, 3784 passed / 46 skipped.
- **Pre-existing defect found, deliberately NOT fixed here** (one concern per PR): `cmd_synthesize` forwards `wiki_sources_dir` but not `log_path` / `state_file` to `synthesize_new_sessions`, so a `--vault` run writes pages into the target vault while appending its log entry to the module-level `WIKI_LOG` fallback. Unrelated to concurrency. Worth a follow-up issue.
- Roadmap left untouched: #118 is not itself a roadmap line item (it is a follow-up to #113 under "Honest pipeline reporting"), so there was nothing to tick.
- **Next:** user smoke confirm, then local dual review.

## scope addition — vault-scoped log path

- At the smoke-confirm gate the user reviewed the pre-existing "always the repo's `wiki/log.md`" defect and **explicitly asked for it in scope of this PR**. Raised the one-concern-per-PR concern; user reaffirmed. Included, and called out as a scope addition in the PR body.
- **Diagnosis corrected one assumption:** `state_file` is *not* affected. `_apply_default_vault` already calls `configure_state_file(args.vault)`, so `resolve_state_file(None)` returns the vault's state file. Only `log_path` was wrong.
- **Four callers shared the bug** — `cli.py` `cmd_synthesize` and `cmd_add`, `pipeline.py` `run_pipeline` (`all --with-synth`), and `queue_ops.py` — each passing `wiki_sources_dir` and no `log_path`. Fixed at the source instead of in four places: the log target now falls back to `sources_out.parent / "log.md"`, the same directory `_rebuild_index(sources_out.parent)` already reconciles. An explicit `log_path` still wins.
- **Default behaviour provably unchanged:** with no vault, `WIKI_SOURCES.parent / "log.md" == WIKI_LOG` (asserted at the console before making the change).
- Two regression tests added; the vault-scoped one was mutation-checked (reverting the fix reddens it, and the explicit-`log_path` test stays green, so it is targeted rather than over-asserting).
- **Side effect confirming the diagnosis:** the worktree's own `wiki/log.md` held at 1070 lines across a full suite run. Before the fix the suite appended to it — the same leak the QA agent had worked around with an autouse fixture.
- Gate after the fix: `ruff` clean, 3786 passed / 46 skipped.
- **Next:** local dual review.

## local review

- **Review files:** `context/spec/005-synth-parallel-and-batch-count/review.md` (checklist, composed from `REVIEW_CHECKLIST.md` + `ARCHITECTURE.md` + `DECLINED.md` + `CONTRIBUTING.md` + `SECURITY.md`) and `context/spec/005-synth-parallel-and-batch-count/review-code-reviewer.md` (independent `code-reviewer`, fixed prompt, no author-supplied focus list).
- **Verdicts:** checklist — changes-requested (1 blocker · 2 important · 9 nits); code-reviewer — approve-with-follow-ups (0 critical · 3 important · 5 below threshold).
- **Both reviews converged on the exception path** — the region with no happy-path signal, where every test, the smoke run, and the byte-identical equivalence check all stayed green because none of them exercises a failure *during* the drain. Two distinct defects, each reproduced at the console before being accepted:
  - Only `KeyboardInterrupt` was caught, so any other escape fell through to `ThreadPoolExecutor.__exit__` → `shutdown(wait=True)`, which drains the whole queue. Reproduced: a failure on completion 2 of 50 still made **all 50** backend calls before the traceback surfaced.
  - `cancel_futures=True` cancels only *queued* futures, so completed-but-undrained ones had written their page with no state entry — re-synthesized and re-billed on the next run. Reproduced: 3 pages written, 1 recorded. Broader than the finding stated (not just in-flight futures), which was relayed to the applying agent.
- **Accepted and applied:** both exception-path defects (unified into one handler + `_record_abandoned_pages`, with 3 regression tests, each mutation-checked red-then-green); the stale `_isolate_synth_log` docstring that described the log-path defect as still open; and spec drift where `technical-considerations.md` §2.1/§4 and `tasks.md` Slice 2 claimed a *missing* `synthesis.concurrency` key warns — the code is right, the documents were amended to match.
- **Declined by the maintainer:** checklist nits 4–10 and 12 (dead optional `concurrency` branch, warning-source label, argparse-vs-body validation placement, `protected:`/`synthesized:` ordering note, `add`'s doubled start line, subprocess-level log-path guard) and every below-threshold code-reviewer item. Recorded here so a later reader knows they were seen and dismissed, not missed.
- Gate after applying: `ruff` clean, **3789 passed / 46 skipped**.

## commit-push

- Per the maintainer's decision at the review gate, the branch is split into two commits so the CHANGELOG's `### Added` and `### Fixed` entries each trace to one: `feat:` for #118's parallel synthesis, `fix:` for the vault-scoped log path. Both reviews raised the bundling; splitting is cheap before push and impossible after merge.
- This is the flow log's last committed state. Everything past this point — PR, CI, merge — is reported in chat and recoverable from the remote state.

## [2026-09-04] fix-bug #186 — fetch / resume / workspace

- **BUG_ID:** 186 — flaky `test_an_interrupt_records_the_pages_that_reached_disk` under full-suite runs
- **URL:** https://github.com/AlexanderMakarov/llm-wiki/issues/186 (OPEN, label bug)
- **Already fixed?** No — issue open; no merged PR for #186 (PR #187 was the #150 feature that flagged it)
- **SPEC_NAME:** `005-synth-parallel-and-batch-count` (owning FR5 interrupt/recovery)
- **BRANCH:** `fix/186-flaky-interrupt-test`
- **WT:** `.claude/worktrees/fix-186-flaky-interrupt-test`
- **TMP_VAULT:** absolute `$WT/.worktree-vault` (isolated config.json)
- **Primary dirty tree:** untracked `.automation/`, `candidates*.png` — warned, not blocking
- **Next:** diagnose

## [2026-09-04] fix-bug #186 — diagnose + classify

- **reproduction:** yes — isolation 25/25 pass; under CPU load 8/25 then 3/12 fail at `assert len(_pages)==len(slugs)` (never state mismatch)
- **root_cause:** brittle test assumes all 3 futures start before KeyboardInterrupt; under contention `cancel_futures=True` cancels a queued item → 2 pages on disk, state matches
- **race_or_test:** brittle test (product `_record_abandoned_pages` invariant held)
- **classification:** **Conformance** — FR5 interrupt/recovery is correct; test over-asserted; no functional-spec amend
- **fix_shape:** use `_BarrierBackend(parties=len(slugs))` so all workers enter before interrupt (preferred); alt: lower-bound + set-membership
- **Next:** fix (testing-expert / generalPurpose) then regression stress

## [2026-09-04] fix-bug #186 — fix + stress + verify

- **Fix applied:** in `test_an_interrupt_records_the_pages_that_reached_disk`, swapped `_RealPageBackend()` for `_BarrierBackend(len(slugs))` (test-only change, `tests/test_synth_parallel.py`). All 3 workers must now enter the backend — leave the pool's pending queue — before any can return, so none can still be a cancellable pending future when the first `_save_state` call raises `KeyboardInterrupt`. Added a docstring paragraph citing #186 with the mechanism, kept the resume assertions unchanged.
- **No production code touched** — confirms the Conformance classification: `_record_abandoned_pages` and the interrupt/drain path in `llmwiki/synth/pipeline.py` are correct as shipped.
- **Stress evidence:** 30/30 sequential runs of the fixed test alone; 30/30 runs of the interrupt/drain/abandoned subset under 8 busy-loop background processes (one per core); 20/20 full-file (`test_synth_parallel.py`, 44 tests) runs under the same load. Zero failures across all three passes.
- **Gate:** `ruff check llmwiki tests scripts` clean; `python3 -m pytest tests/test_synth_parallel.py -q` — 44 passed.
- **Next:** local review, then commit-push (not done in this session — worktree left uncommitted per instructions).

## [2026-09-04] fix-bug #186 — fix + regression + verify-criteria

- **fix:** `tests/test_synth_parallel.py` — `_RealPageBackend` → `_BarrierBackend(len(slugs))` + #186 docstring; product untouched
- **context:** flow-log entries (AWOS gate for tests/ touch)
- **regression:** same test is the regression; stress 30/30 alone, 30/30 interrupt subset under load, 20/20 full file under load
- **criteria checked:** FR5 interrupt AC only — resume does not redo completed sources; disk/state invariant
- **amend-spec:** skipped (conformance)
- **Next:** user smoke confirm, then local review

## [2026-09-05] fix-bug #186 — smoke confirm

- User confirmed fix OK (test-only; live vault N/A)
- **Next:** local review → keep/drop → commit-push

## [2026-09-05] fix-bug #186 — local review + apply-findings + commit-push

- **Review:** Request changes — 1 Blocker, 2 Nits (`context/spec/005-synth-parallel-and-batch-count/review.md`, session-only #159)
- **Keep/drop:** B1 → no CHANGELOG (test-only; use `test:` title so `pr-lint` skips the gate); N1 → applied (barrier precondition docstring + `assert concurrency >= len(slugs)`); N2 → skipped (flow-log stage bundling left as-is)
- **Classification:** Conformance (product FR5 correct; brittle test only)
- **Commit:** `test:` — `tests/test_synth_parallel.py` + this flow log; no CHANGELOG; review.md not staged
- **Next:** push → rebase onto `origin/main` if needed → open PR → remote gates (no further flow-log appends after PR open)
