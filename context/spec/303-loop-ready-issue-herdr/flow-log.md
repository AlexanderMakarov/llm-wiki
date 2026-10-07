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
