# Flow log — 303-loop-ready-issue-herdr (#296)

## fetch-ticket
- Issue #296 open: Spike herdr-driven serial ready-issue loop
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/296
- No existing PR or prior spec
- Next: resume-detection / workspace

## workspace
- Branch: `feat/296-herdr-ready-issue-loop`
- Worktree: `.claude/worktrees/feat-296-herdr-ready-issue-loop`
- Throwaway vault: worktree `.worktree-vault` via worktree `config.json`
- Next: specs (`/awos:spec`)

## specs (functional)
- Decisions: label is driver `--label` param; queue = open + label + assigned to runner; startup counts; advance = merged PR + post-merge CI green (α); no custom notifier; Python driver; `bug` → `/fix-bug` else `/implement-feature`
- Wrote `functional-spec.md` (Approved)
- Next: `/awos:tech`

## specs (tech)
- Approved with renames: skill `loop-ready-issue-herdr` (disable-model-invocation, no slash command); script `scripts/loop_ready_issue_herdr.py`; docs `LOOP_READY_ISSUE_HERDR.md`; `--poll-seconds` default 300; blockedBy only on assignee candidates; herdr event/wait + GitHub poll hybrid; early-close WARNING + restore; driver owns α (not skill signal)
- Spec dir renamed `303-herdr-ready-issue-loop` → `303-loop-ready-issue-herdr`
- Wrote `technical-considerations.md` (Approved)
- Next: `/awos:tasks`

## specs (tasks)
- Wrote `tasks.md` — 4 implementation slices + Feature Testing & Regression (`testing-expert`); agents mostly `general-purpose` (no python-cli agent hired)
- Informational summary only (no draft Approve gate under `/implement-feature`)
- Spec commit: `6225c50` docs: add spec for #296 loop-ready-issue-herdr
- Next: `/awos:implement`

## implement
- All tasks in `tasks.md` marked `[x]` (Slices 1–5)
- Deliverables: `scripts/loop_ready_issue_herdr.py`, `.claude/skills/loop-ready-issue-herdr/SKILL.md`, `docs/maintainers/LOOP_READY_ISSUE_HERDR.md`, README + CHANGELOG, `tests/test_loop_ready_issue_herdr.py` + `tests/test_303_loop_ready_issue_herdr_acceptance.py`
- Next: `/awos:verify` then user smoke confirm (Step 8)

## local-review
- Review file: `context/spec/303-loop-ready-issue-herdr/review.md` (session-only, not committed)
- Verdict: Request changes — 4 Blockers, 8 Nits
- Keep/drop: keep all except N7; N4 → drop `required` mark entirely (all observed check runs must be green; empty = not ready)
- Applied B1–B3, N1–N6, N8; 44 feature/acceptance tests green
- Next: commit-push (flow-log finalized in that commit)

## follow-up (first launch)
- Fixed merge-status GraphQL unused `$number` (use `$number` + `-F`); clearer queue/params/tab-opened lines; poll-failure message explains worker keeps running
- Approval-gate options after spawn are `/implement-feature` → `/awos:spec`, not the thin loop skill
- Merge into main left conflict markers in CHANGELOG (resolve raced commit); `pr-lint` job `No merge conflict markers` greps all tracked text on the PR head for those markers
- Follow-up: always close worker tab on α (even if agent gone); sweep leftover `issue-N` before spawn; `--dry-run` planned queue; skipped Make wrappers (argument-only targets not more convenient than the script)

## fix-bug: adopt open issue-N tab (no GH issue, per operator)
- Bug: after reboot herdr restored in-progress worker tab `issue-307`; re-running the driver closed it ("Closed leftover herdr tab … before spawn") and re-prompted a fresh agent, restarting the ticket. Expected: adopt the open tab, no new prompt, poll for α.
- SPEC_NAME: `303-loop-ready-issue-herdr` (owning spec); resume preflight: not fixed on `origin/main` 8216584
- Workspace: branch `fix/loop-ready-adopt-worker-tab`, worktree `.claude/worktrees/fix-loop-ready-adopt-worker-tab`, throwaway `.worktree-vault`; candidate fix carried over from main checkout as uncommitted patch
- Next: diagnose

## diagnose
- Reproduced on `origin/main` with fake herdr: `tab list → tab close → tab create → agent start → agent prompt`
- Root cause: `spawn_worker_for_issue` unconditionally called `close_existing_issue_tabs` (added in #320 follow-up), treating any open `issue-N` tab as stale; `run_main_loop` had no adopt path
- Candidate fix right shape; follow-ups: multi-tab warning wording (sweep closes others on advance), deliberate error when `tab list` fails, adopted line should say "close to restart". Rejected finding: pane `agent` key — live `herdr pane list` does emit top-level `agent` while an agent runs
- Next: classify

## classify
- Verdict: **Divergence** — spec §2.5/§2.8 never covered a driver restart with an open `issue-N` tab; the #320 "sweep leftover before spawn" behavior was recorded only here and in docs. New behavior (adopt, no re-prompt) gets an acceptance criterion via `/awos:spec` amend
- Next: fix

## fix + regression-test
- `adopt_existing_worker` (reuse open `issue-N` tab, pane with agent preferred, no prompt) replaces pre-spawn `close_existing_issue_tabs`; `tab list` failure refuses to spawn (RuntimeError); multi-tab warns, sweep on advance closes extras; adopted line says "close it to restart"
- Tests: `test_acceptance_run_main_loop_once_single_worker[spawn|adopt]` (adopt case fails on `origin/main`), two `adopt_existing_worker` unit tests (tab-list error, multiple tabs); 50 pass, ruff clean
- Next: verify-criteria

## verify-criteria
- Live read-only: `adopt_existing_worker(#307)` → tab `wD:tR`, agent pane `wD:p5A`; unknown issue → None; `--dry-run --label self-heal` unchanged (next #307)
- Next: smoke confirm, then amend-spec
- Smoke confirm (operator): bare `issue-323` herdr tab + `--once` from worktree → "adopted (…, no new prompt; close it to restart)", no new tab, gone-warning, keeps polling. Earlier run with no open tab spawned `issue-323` normally (unchanged path); its prompt did not land — likely Cursor first-run in a never-opened worktree cwd, pre-existing spawn behavior, out of scope (follow-up: verify prompt delivery)
- Next: amend-spec

## amend-spec
- `/awos:spec` update mode: §2.5 "Driver restart" bullet + 5 checked criteria; new `## Change Log` 2026-10-07 entry; Author/Status unchanged; evidence pinned to concrete test names
- Next: local-review

## local-review
- Review file: `context/spec/303-loop-ready-issue-herdr/review.md` (session-only, not committed)
- Verdict: Approve — 0 Blockers, 2 Nits; keep/drop: keep N1 (gone-warning restore text covers tab-closed case) + N2 (CHANGELOG release note mentions adopt); observations O1/O2 dropped
- Applied N1, N2; ruff clean, full suite green
- Next: commit-push → PR (Refs #296; no dedicated issue per operator). Tracked flow-log ends here.

## fix-bug: keep worker tabs in sync with issue state (no GH issue, per operator)
- Bugs: (1) `issue-N` tabs for issues closed outside the driver (driver stopped/killed) are never closed — re-runs only see open issues (issue-280, issue-307 tabs lingered); (2) wait loop silent: a merged PR with "Relevant to #N" never satisfies α, driver polls forever printing nothing (#323/#335); (3) waited-on issue closed by any means never advances
- SPEC_NAME: `303-loop-ready-issue-herdr`; not fixed on `origin/main` 0dd2af7
- Workspace: branch `fix/loop-ready-issue-state-sync`, worktree `.claude/worktrees/fix-loop-ready-issue-state-sync`, throwaway `.worktree-vault`
- Next: diagnose

## diagnose
- Reproduced with fakes (scratchpad `repro.py`): orphan `issue-99` tab never closed by `run_main_loop(once)`; `wait_until_ticket_advanced` with merged=false polls silently forever
- Root causes: `close_worker_tab` only after α of the waited issue (no startup/cycle sweep); `list_labeled_open_issues` is open-only; merge GraphQL lacks issue `state`; wait loop has no closed-issue exit and no per-poll output
- Fix shape: issue `state`/`stateReason` in merge query; wait order = merged closing PR → strict α (CI) > CLOSED → advance, CI gate skipped > keep waiting; per-poll status line; batched closed-issue tab sweep (one `tab list` + GraphQL aliases) at the top of each cycle (first = startup), before a ticket is picked — so it never touches the waited issue, which is always OPEN; warn-only on errors
- Decision: sweep CLOSED issues' tabs even if their merged PR's CI is still pending (queue never returns to them; today they are orphaned)
- Next: classify

## classify
- Verdict: **Divergence** — §2.8 only defines advance via merged closing PR + CI; closed-without-closing-PR advance and closed-issue tab sweep are new behavior → amend §2.5/§2.8
- Next: fix

## fix + regression-test
- Merge query returns `issue_state`/`state_reason`; wait loop: merged closing PR → strict α; else CLOSED → advance (`closed: <reason>, no merged closing PR; CI gate skipped`); per-poll status line (`format_advance_poll_line`); `list_issue_tabs` + `fetch_issue_states` (batched GraphQL aliases) + `close_tabs_for_closed_issues` at the top of every queue cycle (first = startup), warn-only
- Tests: 62 pass, ruff clean; 13 new/changed cases fail on `origin/main` (wait decision ×3, poll line ×3, sweep ×4, fetch state, 2 acceptance)
- Next: verify-criteria

## verify-criteria
- Live read-only: #323 → `issue_state=OPEN`, no merged closing PR (poll line "#323 open; no merged PR closes it yet — waiting 300s"); `list_issue_tabs` → `[(wD:tX, 323)]`; `fetch_issue_states([280,307,311])` → CLOSED, CLOSED, OPEN
- Next: smoke confirm
- Smoke (agent-run, operator-authorized 2026-10-08): dummy `issue-307` tab + `--once --poll-seconds 30` from worktree → "Closed herdr tab issue-307 (…): #307 is closed."; `issue-323` adopted; "#323 open; no merged PR closes it yet — waiting 30s"; #323 closed on GitHub (delivered by #335, mislinked "Relevant to") → "Advanced #323 (closed: COMPLETED, no merged closing PR; CI gate skipped); worker tab closed.", exit 0, no `issue-*` tabs left
- Next: amend-spec

## amend-spec
- `/awos:spec` update mode: §2.8 advance = merged closing PR + green CI, or CLOSED with no merged closing PR (CI gate skipped); per-poll status line; manual-stop bullet notes issue close counts as delivery. §2.5 orphan sweep (+ warn-only errors). 4 checked criteria; Change Log 2026-10-08
- Next: local-review

## local-review
- Review file: `context/spec/303-loop-ready-issue-herdr/review.md` (session-only, not committed)
- Verdict: Comment — 0 Blockers, 3 Nits; keep all: N1 `fetch_issue_states` tolerates `gh` exit 1 with partial GraphQL data (verified live: aliases 323 + PR 335 → `{323: CLOSED}`), test fake now matches real `gh`; N2 flow-log sweep wording; N3 PR link
- ruff clean, full suite green
- Next: commit-push → PR. Issue link: `Relevant to #296` — follow-up to spec 303 (no dedicated issue per operator); #296 itself is not completed by this PR. Tracked flow-log ends here.

## fix-bug: resume in-progress ticket before queue head (no GH issue, per operator)
- Bug (live 2026-10-09): herdr restored `issue-311` (in progress); #256/#275 became eligible since; `sort_key` puts #256 first; `adopt_existing_worker` only checks the picked issue's tab → driver spawned `issue-256` alongside `issue-311`, violating §2.5 "at most one ticket agent runs at a time"
- SPEC_NAME: `303-loop-ready-issue-herdr`; not fixed on `origin/main` b054d7f
- Workspace: branch `fix/loop-ready-resume-in-progress-first`, worktree `.claude/worktrees/fix-loop-ready-resume-in-progress-first`, throwaway `.worktree-vault`
- Next: diagnose

## diagnose
- Reproduced (scratchpad `repro_resume_first.py`): candidates [256, 311] + open `issue-311` tab → `issue-256` spawned
- Root cause: `run_main_loop` picks via `pick_next` (queue order only); `adopt_existing_worker` only checks the picked issue's tab; sweep's `list_issue_tabs` result discarded; dry-run never reads tabs
- Decisions: resume-first = eligible issues with an open `issue-N` tab, in queue order, before `pick_next`; several → adopt first, warn naming the rest; open tab for an OPEN but non-eligible issue → warn once, ignore; dry-run reads `herdr tab list` (read-only), marks in-progress, degrades to queue order if herdr unavailable
- Next: classify

## classify
- Verdict: **Divergence** — §2.5 "at most one ticket" violated, but resume-first ordering, non-eligible tab and multi-tab rules, and dry-run in-progress marking are unspecified → amend §2.5/§2.9
- Next: fix

## fix + regression-test
- `pick_next_resume_first` (in-progress = eligible issues with open `issue-N` tab, queue order; several → warn), `warn_ineligible_open_tabs` (once per issue), one `herdr tab list` per cycle shared with the closed-issue sweep; `--dry-run` reads tabs read-only, marks "(in progress, tab open)", degrades to queue order when herdr is missing/errors; `adopt_existing_worker` unchanged
- Tests: 71 pass, ruff clean; `test_acceptance_run_main_loop_resumes_in_progress_before_queue_head` fails on `origin/main` (spawns `issue-256`), plus helper/dry-run cases
- Next: verify-criteria

## verify-criteria
- Live smoke (agent-run, read/adopt only, `--once --poll-seconds 60`, stopped by timeout): tabs `issue-311` + `issue-256` open → WARNING naming #311, adopted `issue-256` (no new prompt), "#256 open; no merged PR closes it yet — waiting 60s"; no tab created; both tabs left as found
- Next: smoke confirm (operator), amend-spec
- Operator decision (2026-10-09): several in-progress tabs resume oldest first, not queue order — "#311 was opened yesterday … respect it". herdr has no tab creation time; use tab `number` (tab-bar position; new tabs append, restore keeps order; dragging reprioritizes), tie-break `tab_id`. Live dry-run: next #311 (oldest tab), #256 waits
- Next: amend-spec

## amend-spec
- `/awos:spec` update mode: §2.5 "Resume first" (oldest tab, ineligible tab warn) + 4 criteria; §2.9 dry-run requirement + 1 criterion (evidence incl. `missing`/`error` herdr-unavailable cases); Change Log 2026-10-09; Author/Status unchanged
- Next: smoke confirm (operator), then local-review
- Smoke confirm (operator, 2026-10-09): worktree driver, tabs issue-311 + issue-256 open → WARNING "resuming #311 first (oldest tab) … (#256) wait their turn", `issue-311` adopted (wD:tY, no new prompt), "#311 open; no merged PR closes it yet — waiting 300s"; no tab created
- Next: local-review

## local-review
- Review file: `context/spec/303-loop-ready-issue-herdr/review.md` (session-only, not committed)
- Verdict: Comment — 0 Blockers, 4 Nits; keep all: N1 single CHANGELOG *Fixed* entry (oldest tab first); N2 PR link; N3 `test_open_tabs_by_issue_picks_oldest_open_tab` (each case fails under its mutation: closed filter, tab-order compare, missing-number sort); N4 ineligible-tab warning covers closed issues
- ruff clean, full suite green (`ruff format` not enforced in CI)

## commit-push
- Issue link: `Relevant to #296` — spec-303 follow-up with no dedicated issue (per operator); does not complete #296
- Next: PR. Tracked flow-log ends here.
