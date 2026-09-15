# Flow log — 009-one-call-per-source-synth (#147)

Memory of the `/implement-feature` run outside the context window. One entry per completed stage. Finalized at the commit-push stage — nothing is appended once the PR is open.

## fetch-ticket

- **Ticket:** GitHub Issue #147 — "Collapse synthesis to one model call per source: emit topics, kind, facts and description together" (`important`, state `OPEN`), https://github.com/AlexanderMakarov/llm-wiki/issues/147
- No comments. Related issues fetched: #103 (closed — promote Key Facts LLM), #145 (open — interrupt skips harvest + stale Home counts; **in scope**), #146 (open — discard reasons; out of scope), #148 (open — merge-stitched descriptions; out of scope), #149 (open — apply batch order; out of scope), #109 (closed — descriptions arrive here).
- Unreachable links: none.
- **Next:** resume-detection.

## resume-detection

- Issue OPEN; no `context/spec/*` directory for #147; no matching PR; no `feat/147-*` worktree. Nothing to resume — full chain from workspace.
- Primary checkout was `behind 1` with untracked `candidates.png` / `candidates-top.png` (not a blocker).
- **Next:** workspace.

## workspace

- **Branch:** `feat/147-one-call-synth` off `origin/main` @ `0f2b710`
- **Worktree:** `.claude/worktrees/feat-147-one-call-synth`
- **Throwaway vault:** `<WT>/.worktree-vault`, worktree `config.json` points at it; `llmwiki init` seeded it. `setup.sh` needed `chmod +x` (not executable in a fresh worktree). `LLMWIKI_SKIP_AUTOMATION=1 ./setup.sh`; pytest `-q` green.
- **Next:** specs.

## specs — functional spec

- **Artifact:** `context/spec/009-one-call-per-source-synth/functional-spec.md` (`SPEC_NAME=009-one-call-per-source-synth`)
- **Decisions taken with the user:**
  - Existing source summaries: **rewrite on the next synth** so the whole vault matches the new shape; afterwards skip when already up to date.
  - Known-names list: **once per run**, from disk at start. No mid-run waves and no “2 new stubs → rebuild”. Convergence is **Ctrl+C then restart** (or the next run).
  - Description refresh from fact-count threshold: **do not implement**.
  - `consolidate-topics`: **remove from the product** (not a CLI function-call wrapper). Skills must not tell the agent to run a leftover consolidate step.
  - #145 is **in scope** (harvest on interrupt; Home counts recover on the next site rebuild).
- Spec carries FR1–FR10.
- **Gate:** user approved ("approve"), 2026-08-15.
- **Amendment (2026-08-16):** FR5 / honest accounting updated after tech review — job 1 is one LLM ask per run to prepare known-names; not a free disk-only assembly.
- **Next:** `/awos:tech`.

## specs — technical considerations

- **Artifact:** `context/spec/009-one-call-per-source-synth/technical-considerations.md`
- **Design:** two LLM jobs per `synth` run — (1) `prepare_known_names` once at start (classifier + consolidate + “what is this name”), (2) source page per queued raw file with kind/facts/description on Connections bullets. Harvest/promote are parsers + move. Interrupt returns summary + harvest, exit 130; build refreshes stale `on_disk` (#145). `consolidate-topics` CLI retired (library remains for job 1).
- First draft wrongly treated this as adding a `## Topics` block beside Summary/Claims/Quotes/Connections; user corrected (Karpathy ingest + 4→2 prompts). Claims/Quotes left unchanged.
- **Gate:** user approved ("lgtm"), 2026-08-16.
- **Next:** `/awos:tasks`.

## specs — tasks

- **Artifact:** `context/spec/009-one-call-per-source-synth/tasks.md`
- Eight slices: parser → harvest offline → promote offline → job 1 + retire CLI → job 2 + FR2 rewrite → interrupt/#145 → docs → Feature Testing & Regression (`testing-expert`). Implementation tasks: `general-purpose` (no Python specialist hired).
- Draft Approve ask suppressed per delivery-flow Local Customization.
- **Next:** commit-specs.

## commit-specs

- Spec dir committed as `220ccdb` (`docs: add spec for #147 one-call-per-source synthesis`).
- **Next:** implement.

## implement — slices 1–7

- **Worktree:** `.claude/worktrees/feat-147-one-call-synth` on `feat/147-one-call-synth`.
- Slices 1–7 complete (`tasks.md` all `[x]` except Slice 8). Uncommitted product + docs + tests in the worktree (parser, offline harvest/promote, job 1+2, interrupt 130, `on_disk` mismatch, CHANGELOG/docs/agent-kit).
- `context/product/architecture.md` §6 Testing stack added so Feature Testing is not blocked (pytest unit/integration; Playwright only when UI changes).
- **Next:** Slice 8 `testing-expert`.

## implement — slice 8

- **Added:** `tests/test_147_acceptance.py` (10 tests, `@spec: 009-one-call-per-source-synth`). Slice 8 `[x]`.
- **Next:** verify.

## verify

- Dummy `synth` on throwaway `.worktree-vault`: 3 sources → harvest SharedThing → `promote` exit 0 with Dummy; Connections parseable; `consolidate-topics` exit 2 and `--complete` writes no cache; FR2 rewrite then skip on a non-stub parseable page; `build` after seeded `on_disk: 0` shows Home ON DISK total 4.
- Visual: `docs/screenshots/009-one-call-per-source-synth-home-on-disk.png` (Eligible sources table, ON DISK total 4).
- Spec Status → Completed; roadmap item checked.
- CHANGELOG Unreleased: dropped the superseded “promote requires LLM (#103)” current-tense bullet so it does not contradict #147.
- **Flow correction (2026-08-16):** verify must not capture screenshots and must not start an HTTP server (#109). Recorded in `delivery-flow.md` §2 / §7 / §10; overlays on `/awos-verify` wrappers; implement-feature / fix-bug verify stages. Deleted the Home screenshot taken during the earlier verify pass.
- **Next:** user smoke confirm (open `<vault>/site/index.html` — no server). Do not start local review until confirmed.

## drive-by — install-automation profile B → synth

- Profile B still chained deprecated `synthesize` (sources-only). Switched to `synth` + docs/CHANGELOG/tests.
- Broader first-time UX (lean/full profiles, lint/graph addons, token trade-offs) deferred to https://github.com/AlexanderMakarov/llm-wiki/issues/156 — not in #147 scope.
- **Next:** continue PR delivery for #147.

## commit-push

- `ruff check` + full `pytest tests/ -q` green in worktree (2026-08-23).
- Committing product implementation (exclude `config.json` / `.worktree-vault/`); rebase onto `origin/main` (#155 roadmap); open PR; wait CI.
- Do not merge without explicit user approval.

## #181 fix-bug — fetch-bug / resume-detection / workspace / classify (2026-09-15)

- **Bug:** https://github.com/AlexanderMakarov/llm-wiki/issues/181 — synth clean stop on Ctrl+C **or backend usage limit**: finish in-flight pages, match success-path bookkeeping. Issue body extended the same day to cover the usage-limit trigger (a scheduled run hit the Claude session limit part-way through its queue and still dispatched every remaining source, each failing in under a second).
- **Resume preflight:** issue open; no PR references #181; no prior #181 entries in this log.
- **SPEC_NAME:** `009-one-call-per-source-synth` (FR5 in-flight pages on Ctrl+C, FR6 interrupt recovery, FR9 progress/failure reporting). No `skip-tests` marker in `tasks.md`.
- **Workspace:** branch `fix/181-synth-clean-stop`, worktree `.claude/worktrees/fix-181-synth-clean-stop` from `origin/main` @ `f764777`; throwaway vault `.worktree-vault` (absolute path in worktree `config.json`).
- **Classification: divergence.** Spec 009 defines the clean stop for Ctrl+C only, and FR9 says a failed source pass is reported while other sources still complete. A backend usage limit becomes a second clean-stop trigger that halts the queue instead of continuing, with its own reporting and exit code → amend FR6/FR9 (and FR5's in-flight criterion) via `/awos:spec` update mode after the fix.
- **Next:** diagnose (subagent running) → fix.

## #181 fix-bug — diagnose (2026-09-15)

- **Repro (usage limit):** fake backend succeeds 3× then raises the real 429 `ClaudeCLIError` text; 20 sources, concurrency 2 → 20 backend calls, 3 synthesized, 17 errors, not interrupted. All futures are submitted up front; `_synthesize_one` (`llmwiki/synth/pipeline.py`) catches every `Exception` into `result["error"]` and the drain `continue`s.
- **Backends:** no shared error base in `synth/base.py`. Claude surfaces a limit on the non-zero-exit branch and on the `is_error` branch of `_parse_claude_print_stdout` (neither reads `api_error_status`). Cursor/Ollama have no recognisable limit signal.
- **Ctrl+C gaps:** no recording race (`_record_abandoned_pages` blocks on `result()`), but the interrupt path skips the `wiki/log.md` summary entry and `take_usage`, undercounts `synthesized` for pages recorded after the interrupt, and skips `print_synth_run_summary`; `llmwiki all` ignores `summary["interrupted"]` (can exit 0 after Ctrl+C). Terminal Ctrl+C also SIGINTs `claude -p` / `cursor-agent` children (same process group), so in-flight pages likely fail instead of finishing (inferred, not run). `synth` never builds `site/` on success — confirmed.
- **Exit codes:** synth 0/1/2/130; `all` merges first non-zero but a lint policy failure returns 2 directly, masking earlier codes; the automation wrapper's `EXIT:$?` line never prints a non-zero code under `set -e`.
- **Scope decision (orchestrator):** in — `BackendUsageLimitError` (reset time) raised by the Claude backend; pipeline stops dispatching on the first one and drains in-flight work through the normal success tail; Ctrl+C moved onto the same tail; `deferred` + `usage_limit` in the summary with one stop line; `synth` exits **75** (EX_TEMPFAIL) after harvesting; `all` propagates 130/75 and lint merges instead of overriding; child CLIs start in their own session so a terminal Ctrl+C lets them finish; automation wrapper records the real exit code; docs/CHANGELOG/UPGRADING. Out — second Ctrl+C during drain, Ollama 429 mapping, stale #171 test.
- **Next:** fix (subagent) → regression tests.

## #181 fix-bug — fix (2026-09-15)

- **Changed:** `llmwiki/synth/base.py` (`BackendUsageLimitError` + `reset`), `synth/claude_cli.py` (limit detection on exit-1 and `is_error` branches; page calls `start_new_session=True`), `synth/cursor_cli.py` (`start_new_session=True`), `synth/pipeline.py` (one stop path for both triggers: shared `stop_event` checked by workers before the backend call, queue cancelled once, in-flight drained through normal handling, then the success tail; `deferred` / `usage_limit` summary keys; log title suffix `— stopped early (…)` + `- Deferred: N`; `synth_stop_exit_code()` → 130/75), `cli.py` (synth harvests on either stop, returns 130/75), `pipeline.py` (`all` propagates 130/75; lint failure merges via `_merge_rc`), `automation_install.py` (wrapper logs and exits with the real code), docs (`docs/reference/cli.md`, `docs/UPGRADING.md`, CHANGELOG **Breaking:**, `agent_kit/commands/wiki-synth.md`), existing-test updates (`tests/test_automation_install.py`, `tests/test_synth_run_summary.py`).
- **Evidence:** repro through the real Claude CLI parser → 3 synthesized, 17 deferred, 0 errors, exit 75, reset parsed; SIGINT to the parent's process group — child in its own session finishes (rc 0) vs killed without (rc -2); timeout still kills the child. `ruff` clean; pytest 5212 passed / 48 skipped / 0 failed (wheel test needing `pip` deselected).
- **Decisions:** `stop_event` needed because cancelling futures does not stop a worker that already dequeued; a second Ctrl+C during drain keeps the save-and-reraise path (`_record_abandoned_pages` kept); `all --fail-fast` on a stop harvests then returns 75/130; the Claude overview call keeps the default session; limit text matched only inside the JSON result.
- **Next:** regression tests (testing subagent).

## #181 fix-bug — regression-test / verify-criteria (2026-09-15)

- **Regression tests:** `tests/test_181_synth_clean_stop.py` — 13 tests (pipeline usage-limit stop, generic failure still continues, Ctrl+C drain + log entry, Claude limit parsing on both branches + `start_new_session`, `synth` exit 75/130 with harvest / `--sources-only` hint, `all` propagates 75/130 over a lint failure, wrapper logs and exits with the real code). Core tests red on `origin/main` (scratch worktree), green on the fix; with neighbouring suites 127 passed; ruff clean.
- **Verify (real CLI, throwaway vault, stub `claude` emitting the real 429 JSON):** `synth` over 12 docs, 3 successes then limit → one stop line with reset time, 3 synthesized, 9 deferred, 5 backend calls (2 limit hits = concurrency), exit **75**, harvest ran, one `wiki/log.md` entry `— stopped early (backend usage limit)` + `- Deferred: 9`. `all --no-sync --skip-graph --lint-fail warnings` with the limit from the first call → known-names prep warns and falls back to heuristic vocabulary, first page round stops the run, build + lint still run, lint policy fails but exit stays **75**.
- **Verify incident:** a first `all` run without `--no-sync` synced local agent sessions into the throwaway `.worktree-vault` (worktree config carries no adapter filters). Vault deleted and re-initialised; nothing tracked or pushed. Use `--no-sync` for `all` verifies in worktrees.
- **Observed nits (for review):** the stop line's in-flight count misses a page that finished but is not drained yet; when the limit hits known-names prep, one round of page calls still goes out before the stop.
- **Next:** user smoke confirm (live Ctrl+C with the real `claude`), then local review.

## #181 fix-bug — smoke confirm (2026-09-15)

- **Operator smoke on a private vault with the real `claude` CLI (state + wiki backed up first), terminal Ctrl+C, worktree code:** works — in-flight pages finished, deferred count printed, rc 130, log entry `N sessions across M projects — stopped early (interrupted)`. Worktree config confirmed restored afterwards.
- **Operator questions answered:** (a) the ~1 min pause before `Synthesizing N source(s)` is the known-names preparation LLM call (`.llmwiki-topics.json` written just before the run's first page), not an adapter — candidate for a separate issue (progress line / size or timeout); (b) `synth` does not build `site/` on success or stop — unchanged, `all` builds; (c) Ctrl+C clean stop works for every backend; usage-limit detection is Claude-only (Cursor exposes no recognised quota output, Ollama has no quota).
- **Noted (pre-existing, not in scope):** the synth log title counts projects across all queued sources, not the synthesized ones — more visible on an early stop.
- **Next:** amend spec 009 (divergence) → local review.

## #181 fix-bug — amend-spec (2026-09-15)

- **Divergence amendment** applied to `functional-spec.md`: FR5 in-flight criterion covers both stop triggers; FR6 retitled "Stopping synthesis early…", requirement text + two new criteria (single stopped-early history entry with deferred count; scheduled full run keeps the usage-limit status and still rebuilds the site); FR9 non-limit failure carve-out + usage-limit stop-line criterion; In-Scope interrupt bullet generalised; Out-of-Scope adds non-Claude limit recognition and site rebuild inside synthesis; new `## Change Log` entry. Status stays Completed; Author unchanged.
- **AWOS framework defect (reported to the user, not patched):** `/fix-bug` Step 9 says `/awos:spec` has an Update Mode reached via Mode Detection, but the in-repo `.awos/commands/spec.md` only creates new specs (no mode detection, no Change Log step). Amendment was done by hand in the documented shape.
- **Next:** local review (independent subagent).

## #181 fix-bug — local review (2026-09-15)

- **Review:** independent reviewer, `review.md` (session-only, not committed). Verdict Request changes — 1 blocker, 6 nits.
- **Operator keep/drop:** B1 (real timezone in a code comment) kept; N6 (live-vault stats in this log) kept; N1 (Ctrl+C during result bookkeeping could drop a written page from state) kept; N4 (usage limit during known-names prep still sent a page round; approximate in-flight count) kept; N2 changed by operator — a second Ctrl+C kills in-flight synthesizer child processes; N3 changed by operator — usage-limit detection by message text in every backend (Claude, Cursor, Ollama), a bare HTTP 429 is not enough; N5 dropped — regular PR, no label, no size waiver. Orchestrator addition: UPGRADING exit-code wording (earliest failing step wins, not a priority list).
- **Next:** static gate → commit-push.

## #181 fix-bug — review fixes / commit-push (2026-09-15)

- **Applied:** B1 + N6 privacy scrub; N1 idempotent per-result recording + post-drain reconcile, `deferred` = total − synthesized − failed; N4 usage limit during known-names prep stops before any page call; N2 tracked synthesizer child processes (`llmwiki/synth/child_processes.py`), second Ctrl+C / abandon path kills their process groups; N3 shared usage-limit text matcher in `synth/base.py` used by Claude, Cursor and Ollama (bare 429 / throttling stays a per-source error); operator follow-up — progress line before known-names preparation with candidate count and prompt size. Docs, CHANGELOG, UPGRADING wording and spec 009 FR6/Out-of-Scope/Change Log updated.
- **Follow-ups filed:** #264 (bound known-names preparation — candidate cap, incremental reuse, own timeout), #265 (migration for source pages filed under a stale slug that synth skips every run).
- **Gate:** `ruff check` clean; full pytest green (wheel test needing `pip` deselected — shared venv has no `pip`).
- **Next:** commit, rebase onto `origin/main`, push, open PR. No further entries in this log after the PR opens.
