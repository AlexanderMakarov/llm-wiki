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
- Merge into main left conflict markers in CHANGELOG (resolve raced commit); added `tests/test_no_merge_conflict_markers.py` + pr-lint CHANGELOG grep so CI catches that next time
