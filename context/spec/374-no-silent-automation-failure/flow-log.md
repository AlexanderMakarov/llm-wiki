# Flow log — #374 automation never fails silently

## fix-bug #374 — diagnose, classify, fix, regression test (2026-10-31)
- Bug: [#374](https://github.com/AlexanderMakarov/llm-wiki/issues/374) — scheduled synth stopped (`backend claude-cli is not available`) once Claude Code's self-update deleted the version binary `install-automation` had pinned in `synthesis.claude.path`.
- Branch `fix/374-claude-path-pin` (renamed below), worktree `.claude/worktrees/fix-374-claude-path-pin` (moved below), throwaway vault `.worktree-vault/`.
- Spec: fix-as-spec directory (no functional spec owns #275's pin). No functional-spec to amend.
- Root cause: `cli._maybe_pin_claude_path` stored `resolved.resolve()`, which follows the `~/.local/bin/claude` launcher symlink to `versions/<X.Y.Z>`. Reproduced on `main` with a synthetic `bin/claude -> versions/1.0.0` layout.
- Classification: **conformance** — #275 promises a pin that keeps scheduled synth finding the CLI; following the symlink broke that after the first pruning update.
- Fix: store `resolved.absolute()` (absolute, symlinks kept).
- Regression test `tests/test_automation_install.py::test_yes_claude_pins_the_launcher_not_the_versioned_binary_it_links_to` — fails on `main` (pin is `versions/1.0.0`), passes on the fix; it also repoints the launcher and deletes the old version, and the pin still resolves. The #275 test now expects the unresolved launcher path.
- #275 is unreleased, so its CHANGELOG entry, `docs/UPGRADING.md` section and `docs/configuration-reference.md` row are rewritten to the final behaviour; UPGRADING tells users with an earlier versioned pin how to repair it.
- Next: static gate, local review.

## fix-bug #374 — verify touched criteria (2026-10-31)
- Resumed under `/fix-bug 374` (the earlier stages ran without the skill invoked; the local review that ran before smoke confirm is superseded and re-runs after it).
- Static gate: `ruff check` clean; full `pytest tests/` exit 0.
- Real CLI on the throwaway vault, synthetic `bin/claude -> versions/1.0.0` first on `PATH`, `install-automation --yes --job maintain --synth-backend claude --no-activate --units-dir <scratch> --vault <tmp>`: `origin/main`'s `cli.py` pins `versions/1.0.0`; the fix pins `bin/claude`. After repointing the launcher to `versions/1.0.1` and deleting `1.0.0`, `synth --check` under `PATH=/usr/bin:/bin` reports `Available: True`. No unit reached the OS scheduler.
- Next: smoke confirm, local review.

## implement-feature #374 — scope change, workspace (2026-10-31)
- Operator widened #374 from the pin bug to "automation never fails silently": the issue now carries five acceptance criteria (failed stage banner on Home, no rebuild needed, clears on recovery, missed-run detection, pin fix as criterion 5). Flow switched from `/fix-bug` to `/implement-feature 374`.
- Workspace reused: worktree moved to `.claude/worktrees/feat-374-no-silent-automation-failure`, branch renamed `feat/374-no-silent-automation-failure`, spec dir renamed `context/spec/374-no-silent-automation-failure/`; throwaway vault re-pointed. Superseded pre-smoke `review.md` deleted.
- Carried over (uncommitted): the pin fix in `llmwiki/cli.py` (`absolute()`), its regression test, and the #275 CHANGELOG / UPGRADING / configuration-reference edits — criterion 5.
- Next: `/awos:spec` (approval gate).

## implement-feature #374 — functional spec (2026-10-31)
- `functional-spec.md` written and **approved** by the operator (Author: Alexander Makarov). Six requirements, 25 criteria: one red error banner at the top of Home holding run failures, overdue schedule and lint (the lint note moves into it); each entry names the part (Sync/Synth/Build/Lint/Schedule) and entirely vs partly (n of m, which); visible after a browser refresh without rebuild; entries clear when that part next finishes cleanly, scheduled or by hand (partial/trial runs do not clear); overdue after one interval + 2h; every outside program (job runner, Claude CLI, Cursor agent, Ollama) found across updates and reported when missing.
- Operator decisions: banner at top of Home; all failures red, including partial and usage-limit stops; overdue grace 1 interval + 2h, not configurable; a manual full run of a part clears its entry.
- Next: `/awos:tech` (approval gate).

## implement-feature #374 — technical spec (2026-10-31)
- `technical-considerations.md` written and **approved** by the operator. Exploration by `Explore`, Python design checked by `python-development:python-pro` (five fixes folded in: register `outcomes` in `_ensure_shape`; sync partial from per-run counters, not rc; try/finally around the pipeline lock; scheduled `sync` job goes through `cmd_sync`; stamp scheduled run at the end, not the start).
- Operator decisions: an install predating the marker shows a "Schedule — setup outdated" banner entry; the wrapper loads the login profile at run time plus program folders recorded at install (never the whole install-time PATH); overdue re-checked once a minute in an open Home tab.
- Next: `/awos:tasks` (no draft gate), commit specs, implement in the main session (operator CLAUDE.md overrides the skill's delegation).

## implement-feature #374 — tasks, commit specs (2026-10-31)
- `tasks.md` written (no draft gate): 7 vertical slices + Feature Testing & Regression — (1) banner holding the lint note, (2) synth outcomes in `all`, (3) sync/build/run outcomes, (4) manual runs record/clear, (5) schedule marker / overdue / setup outdated, (6) wrapper finds outside programs + doctor, (7) docs.
- Specs committed on `feat/374-no-silent-automation-failure`.
- Next: implement Slice 1 in the main session.

## implement-feature #374 — Slice 1 done (2026-10-31)
- `#llmwiki-problems` mount first in `.queue-widget` (`raw_docs_site.render_dashboard_body`); `render/js.py` pure `problemEntries(snapshot, nowMs)` + DOM `renderProblemsBanner` (textContent only, 10-line clip, malformed snapshot → `__llmwikiReportError`); lint note moved out of the Knowledge table into the banner's Lint entry; CSS `.problems-*`; new `--danger` token (light #b91c1c, dark #f87171 — the old fallback was ~2.4:1 on dark).
- Tests: new `tests/test_home_problems_banner.py` (runs the page's own functions under node); `tests/test_state_widget.py` lint-note assertions updated, two placement tests removed.
- Verify: Playwright on a built `.worktree-vault` with a recorded lint error — banner visible and first in light and dark, no old note, no console errors, ~6.5:1 contrast both themes. Artifacts deleted.
- Next: Slice 2 (synth outcomes in `all`).

## implement-feature #374 — Slice 2 done (2026-10-31)
- `state_store`: `outcomes` registered in `default_state` / `_ensure_shape` (`_shape_outcomes` drops malformed members). New `llmwiki/run_outcomes.py` (`Failure`, `record_failure` / `record_clean` / `record`, `synth_failure`, `synth_unavailable`, `harvest_failure`; 8 KB detail cap; log path only for scheduled runs).
- Backends: `unavailable_reason()` on `BaseSynthesizer` + claude / cursor_cli / ollama; `backend_unavailable_message()` keeps the `backend <name> is not available` prefix; used by `all`, `synth` and doctor; `heal_kb.json` row gains the `is not available:` pattern and fix text.
- `run_pipeline` records synth (unavailable / partial / usage limit / interrupted / harvest) before every `--fail-fast` return; clean clears; `--no-synth` leaves it. Banner renders parts in order Sync, Synth, Build, Run, then Lint.
- Tests: `tests/test_run_outcomes.py` (16), `tests/test_pipeline_outcomes.py` (8), banner parts test. Verify: real `all` with a missing pinned claude path on `.worktree-vault` → rc 1, Home banner "Synth — did not run: backend claude-cli is not available" with the reason; no console errors.
- Next: Slice 3 (sync / build / run).

## implement-feature #374 — Slice 3 done (2026-10-31)
- `run_pipeline` stages moved into an inner `_stages()`; the outer function records a `run` entry on any exception (lock timeout, config error, build crash) and re-raises, and on a non-zero exit that no Sync / Synth / Build entry or lint policy explains, or that has unexplained causes (graph step, lint that could not run, build into a custom `--out`).
- Sync: entire when `convert_all` rc ≠ 0; partial from this run's per-adapter `errored` counters plus quarantine rows with `last_seen >= run start`. Build: entire on rc ≠ 0 or exception, only for the default `--out`. `run_outcomes`: `sync_failure`, `build_failure`, `build_crashed`, `run_crashed`, `run_failure(explained=…)`; `record()` returns whether it stored a failure.
- Tests: `tests/test_pipeline_outcomes.py` now 20. Verify: recorded Sync + Build on `.worktree-vault`, plain browser reload (no rebuild) shows Sync, Synth, Build, Lint in order; no console errors. A real worktree `sync` was not run — the worktree config has no adapter filters and would read the operator's stores.
- Next: Slice 4 (manual runs record / clear).

## implement-feature #374 — Slice 4 done (2026-10-31)
- `cmd_synthesize` records Synth only on a full run (no `--path` / `--sessions-only` / `--docs-only` / `--sources-only`; `--estimate` / `--check` / `--candidates-only` return earlier): unavailable, source errors, stops, harvest rc; clean clears. `cmd_sync` records Sync on a full run (no `--adapter` / `--since` / `--project`) and its auto-build's rc / exception as Build (previously ignored). `cmd_build` records Build only for the default `--out`.
- `sync_failure` now decides from this run's counters whenever `sync.meta.last_sync` is fresh, so `--fail-on-errors`' rc 1 reads as partial, not "did not run".
- Tests: new `tests/test_manual_run_outcomes.py` (20).
- Next: Slice 5 (schedule marker, overdue, setup outdated).

## implement-feature #374 — Slice 5 done (2026-10-31)
- Wrapper exports `LLMWIKI_SCHEDULED_RUN=1`. `run_install` calls `configure_schedule` (marker, `interval_s` from `cron_interval`, grace 7200, `installed_at`, log path) only when the scheduler was activated. `run_pipeline` and `cmd_sync` (scheduled ingest job; body split into `_sync_locked`) run `check_schedule_setup` first and, when scheduled, `stamp_scheduled_run` at the end (exit 1 on a crash).
- `check_schedule_setup`: activated schedule without the marker → `outcomes.setup_outdated`; no activated schedule → schedule records cleared. There is no uninstall command, so this is the only `clear_schedule` caller.
- Banner: "Schedule — overdue" (last run or install + interval + grace, judged by the browser clock, detail names last run and expected-by), "Schedule — setup outdated: re-run llmwiki install-automation"; `setInterval` re-check every 60 s.
- Tests: new `tests/test_schedule_outcomes.py` (11); banner tests now 14. Verify: Playwright with a fake clock on a rebuilt `.worktree-vault` — not overdue at 25 h, an open page turns "Schedule — overdue" 2 h later without reload; no console errors. Found while verifying: a site built before the upgrade carries the old `script.js` until its next build (the next scheduled run rebuilds) — goes into UPGRADING.
- Next: Slice 6 (wrapper finds outside programs, doctor findings).

## implement-feature #374 — Slice 6 done (2026-10-31)
- Wrapper environment (`automation_install._wrapper_environment`): the login profile (`.bash_profile` / `.bash_login` / `.profile`) is read in a child shell with stdin `/dev/null`, a 30 s `timeout` when available and an EXIT trap, so only its PATH comes back — a profile that exits, fails or hangs cannot end the job; then `export PATH=<recorded dirs>:"$PATH"`. `program_dirs()`: backend programs (`claude`; `agent` / `cursor-agent`) then the interpreter, launcher folder kept (no symlink resolution), absolute + existing + deduplicated + `shlex.quote`d; recorded as `program_dirs` in `automation-status.json`. Never the whole install-time PATH.
- Doctor area L: `automation.setup_outdated` (wrapper lacks the marker export), `automation.interpreter_missing` (wrapper's absolute interpreter gone), `automation.program_dir_missing`; heal_kb rows (runner `install_automation`); detector ids registered. The doctor test fixture's fake wrapper now carries the marker, as a current install does.
- Verify: real `install-automation --yes --job maintain --synth-backend claude --no-activate --units-dir <scratch>` with a synthetic `bin/claude -> versions/1.0.0` — pin is the launcher, `program_dirs` recorded, the wrapper's environment block under `PATH=/usr/bin:/bin` finds `claude`. Four profile shapes run under real bash (exits / hangs / none / failing commands). Found while verifying: a non-zero profile exit wiped the captured PATH (`|| var=""`) — fixed to `|| true`; backend folders now precede the interpreter's.
- Next: Slice 7 (docs).

## implement-feature #374 — Slices 7–8 done (2026-10-31)
- Docs: `docs/reference/ui.md` (Home item 1 problems banner; lint note is its Lint entry; published sidecar may hold paths), `docs/reference/cli.md` (wrapper environment + stamping; three new area-L rows), `docs/configuration-reference.md` (`LLMWIKI_SCHEDULED_RUN`), `docs/reference/state-persistence.md` (`outcomes`), `docs/UPGRADING.md` (re-run `install-automation` once; banner arrives with the next build; error text prefix), CHANGELOG *Added* entry with release note.
- Static gate: `ruff check llmwiki tests scripts` clean; full `pytest tests/` exit 0 (coverage floor met). A first run stopped on a function-level stdlib import (PLC0415) in a test helper — hoisted.
- Red validation: 12 rules each removed in turn (full-synth / full-sync guards, sidecar copy, `outcomes` in `_ensure_shape`, marker export, end-of-run stamp, unexplained-rc run entry, sync partial, overdue grace, profile PATH on non-zero exit, launcher folder, doctor setup_outdated) — every one turns its tests red; code restored.
- New `tests/e2e/test_home_problems_banner.py` (5, Chromium): banner first on Home with Synth + Lint, refresh-without-rebuild, open page turns overdue on the fake clock, light/dark colours. Whole e2e suite: 209 passed; 12 `test_visual_regression.py` failures reproduce identically on `origin/main` (screenshot baselines vs this machine), unrelated.
- Next: `/awos:verify`, smoke confirm, local review.

## implement-feature #374 — verify (2026-10-31)
- `/awos:verify` on `.worktree-vault`: 25 criteria marked `[x]`; functional and technical specs set to Completed (ships with the PR — a post-merge flip could not be committed). No roadmap item (issue-driven).
- Evidence (real CLI on the throwaway vault + Playwright): `all` with a gone pinned claude path → "Synth — did not run" with the reason, `doctor --check` names it; `lint --fail-on-errors` adds the Lint entry beside Synth with no separate note (light + dark); `synth --estimate` / `--check` / `--path` leave Synth; a full `synth` (dummy) clears it while Lint stays; Ollama at a dead port → reason names the server; a `LLMWIKI_SCHEDULED_RUN=1` `all` clears everything and stamps; overdue at two days, not at 25 h, an open page turns overdue after 2 h on the fake clock; a manual `all` keeps the stamp; no status → no Schedule entry; Sync / Synth / Build / long detail / usage limit / run-failed entries render after a plain reload; Sync clears while Build stays; no console errors. 2.6: launcher self-update and Cursor `agent` found by the wrapper under `PATH=/usr/bin:/bin`; missing interpreter → overdue (no stamp) + `doctor` test.
- Screenshots (local only, not committed — they show throwaway-vault paths): `docs/screenshots/374-no-silent-automation-failure-*.png`.
- Noted, not changed: the Ollama backend's `name` is its class name (`OllamaSynthesizer`, pinned by an existing test), so its banner entry reads "backend OllamaSynthesizer is not available".
- Next: smoke confirm, local review.

## implement-feature #374 — smoke round 1, root cause, forward-safe state (2026-10-31)
- Smoke round 1 (operator, worktree `all --no-sync --no-synth --skip-graph` on the live vault): `doctor --check` reported `automation.setup_outdated` as expected, but Home showed no banner.
- Root cause, proven read-only: the kbbuilder `llm-wiki-worker` service runs `python3 -m llmwiki queue run --limit 5 --vault <live>` every minute from the main checkout (cwd observed in `/proc`), which is pre-#374 code; `queue_ops` stamps `ops.last_queue_run_at` through `update_state`, and the old `_ensure_shape` rebuilds from its known sections, so each run dropped `outcomes`. Observed: revision 86589 → 86590 at 18:41:01 with `outcomes` True → False and `last_queue_run_at` 14:41:00Z, matching the worker tick at 18:41:00.97.
- Operator chose to include a forward-safe state shape: `_ensure_shape` now keeps unknown top-level sections that are dicts and not `_`-prefixed (legacy flat per-file keys and `_meta` / `_counters` still dropped). Regression test `tests/test_run_outcomes.py::test_state_writes_keep_sections_a_newer_llmwiki_added`, red with the loop removed. UPGRADING: restart long-running llmwiki processes after upgrading; state-persistence doc notes the kept sections.
- Static gate: ruff clean; full suite exit 0.
- Next: smoke round 2 with the worker paused (operator), then local review.
- Smoke round 2 (operator, worker paused): Home shows the red "Schedule — setup outdated: re-run llmwiki install-automation" banner on the live vault. Smoke confirmed.

## implement-feature #374 — local review, commit-push (2026-10-31)
- Independent review (session-only `review.md`): **Comment** — 0 blockers, 6 nits (N1 important). Operator kept all six.
  - N1: a scheduled `sync` (ingest plan) clears the `run` entry after a clean finish; regression test `tests/test_schedule_outcomes.py::test_a_clean_scheduled_sync_clears_an_earlier_crash` (red without the clear).
  - N2: rebased onto `origin/main` (#375) before push.
  - N3: all new modules and tests staged; `docs/screenshots/374-*` kept out (they show throwaway-vault paths).
  - N4: dropped the broad `runs Python` heal pattern.
  - N5: the wrapper also reads `~/.zprofile` through zsh when zsh is installed; `cli.md` states the macOS `timeout` gap and the `.bashrc` / `.zshrc` guard limit; test with a zsh stand-in.
  - N6: `all --out <other>` sends outcome records to the vault's own `site/`; regression test `tests/test_pipeline_outcomes.py::test_outcomes_refresh_the_vault_site_when_out_points_elsewhere` (red without it).
- PR link keyword: `Closes #374` — the issue's five acceptance criteria (failed parts on Home, no rebuild, clears on recovery, missed runs, the pin root cause) are all delivered; the forward-safe state shape is an addition the operator asked for.
