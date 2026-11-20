# Flow log: 417-synth-tests-consolidate (#318)

## workspace
- BRANCH=`feat/318-synth-tests-layout`
- WT=`<worktree>`
- MAIN=`<repo>`
- TMP_VAULT=`<worktree>/.worktree-vault`

## specs
- `/awos:spec` — functional-spec.md approved (operator Accept). Author: 4ellendger.
- `/awos:tech` — technical-considerations.md approved (operator Accept). Author: 4ellendger. Batch: 13 flat modules → `tests/synth/`; stay-put: overview_safety, ollama_backend, `tests/cli/test_synth.py`.
- `/awos:tasks` — tasks.md written (4 slices; no draft Approve ask per implement-feature Local Customization).
- Issue link keyword for PR: `Closes #318` — ticket owns this one migration pass fully.
- Specs committed: `7a9ce66`

## implement
- **Slice 1** — `docs/CODING_STANDARDS.md` names `tests/synth/`; quality-gates DOC assert + package layout gate.
- **Slice 2** — bounded flat batch → `tests/synth/`; `tests._paths.REPO_ROOT` fixes; hygiene dropped 3 duplicate parallel unit cases; usage/interrupt/backend-mock contracts kept; full suite + 87.33% coverage.
- **Slice 3** — extended existing Unreleased mirror-layout CHANGELOG bullets with #318 / `tests/synth/`.
- **Slice 4** — initially added flat-gone inventory gates (wrong); removed after local review B1. Kept DOC + `test_synth_unit_tests_live_under_mirrored_synth_package` only.
- Stay-put: `tests/test_synthesize_overview_safety.py`; ollama; `tests/cli/test_synth.py`.

## verify
- Functional-spec Status=Completed; ACs `[x]` with honest evidence (docstring AC narrowed to hygiene-touched cases).
- Smoke (operator authorized agent-run): ruff + `pytest tests/synth/ tests/test_quality_gates.py` + live `lint --rules index_sync` green.

## local-review
- Review file: `review.md` (session-only, not committed). Verdict: Request changes (1 Blocker, 3 Nits).
- keep/drop: **keep all** (operator). Applied: delete B1 inventory tests; narrow docstring AC (N1); placeholder paths in this log (N2); commit/PR reminders for Step 9 (N3).
- B1 cause: this ticket’s Slice 4 task line asked for flat-gone inventory asserts (copied from an older completed tasks.md). Fix: remove that ask; one-line clarify in `testing-expert` that task text does not authorize inventory tests.

## commit-push
- Issue link keyword: `Closes #318` — issue owns only this one synth unit-test mirror pass; all in-scope ACs delivered (stay-put/overview and ollama explicitly out of issue scope).
- Next: push → open PR → remote gates (stop appending this log after PR opens)
