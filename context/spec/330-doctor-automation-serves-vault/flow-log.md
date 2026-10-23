# Flow log — #359 doctor automation serves vault

## fetch-ticket / resume-detection / workspace
- Issue #359 open, no prior spec or PR.
- Worktree `.claude/worktrees/feat-359-doctor-automation-health`, branch `feat/359-doctor-automation-health` from origin/main 9cdebbf; throwaway vault `.worktree-vault`.

## spec
- `context/spec/330-doctor-automation-serves-vault/functional-spec.md` approved by user (2026-10-22).
- Decisions: install guard included (Closes #359 target); one schedule per vault (legacy single schedule adopted by the vault it serves); points-elsewhere/missing = error; stale run = warning with 2× interval grace; leftover schedules for missing vaults = warning, manual removal only.
- Next: /awos:tech.

## tech
- `technical-considerations.md` approved by user (2026-10-22). Explore + python-pro specialist drafted it.
- Decisions: new `llmwiki/automation_units.py`; per-vault unit ids `llmwiki-maintain-<slug>-<hash8>`; new units always pin `--vault`; `installed_at` resets each activation; any git clone counts as dev checkout (worktree stronger wording); doctor repair argv includes `--yes --force` and shows runs-from + dev warning; new finding `automation.checkout_missing`.
- Next: /awos:tasks (no draft approval gate).

## tasks
- `tasks.md` written: 8 implementation slices (python-development:python-pro) + Feature Testing & Regression (testing-expert). No draft gate per flow.
- Next: commit specs, then /awos:implement.

## commit-specs
- Spec docs committed on `feat/359-doctor-automation-health` (not pushed).
- Next: /awos:implement.

## implement
- All 9 slices / 22 tasks done via subagents (python-pro; testing-expert for Slice 9). Uncommitted working tree on the branch.
- New: `llmwiki/automation_units.py`, `tests/test_automation_serves_vault_acceptance.py` (23 tests). Full suite green, ruff clean.
- Decisions taken during implementation: legacy wrapper without `--vault` and no configured default → target is the checkout itself when it contains `llmwiki/` (mirrors resolve_content_root); `points_elsewhere` names disambiguate same-basename vaults with parent dirs (max 3 components); conftest autouse fixture blocks real scheduler discovery and points XDG_STATE_HOME at tmp; the #359 CHANGELOG entry describes doctor area L as shipped behaviour (doctor itself is unreleased, so no before/after wording).
- Observed pre-existing test leak (also on origin/main): full suite leaves `wiki/` and `demo/wiki/archive/` dismissals.json at repo root; out of scope.
- Next: verify.

## verify
- /awos:verify (subagent): all R1–R8 pass, no gaps; functional + tech spec Status → Completed. macOS/Windows verified by tests only.
- Next: local-review (smoke confirm first).

## local-review
- Smoke confirm: the user asked the agent to run the check; read-only `doctor --check` on the live vault reported `automation.points_elsewhere` for the legacy unit plus the new backlog hint; `doctor --error` mapped all symptoms; `install-automation --no-activate --units-dir <scratch>` on the worktree vault wrote per-vault units.
- One independent reviewer (fixed prompt): Request changes, 2 Blockers / 10 Nits; review file `context/spec/330-doctor-automation-serves-vault/review.md` (session-only, not committed).
- Keep/drop: user kept all findings. Applied: CHANGELOG wording as shipped behaviour (B1); run logs older than `installed_at` ignored and the shared legacy log only for the legacy unit or a unit naming no log (B2); install guard reads unit files even when the scheduler is unreachable (N1); new `automation.duplicate_legacy` (N2); shared `serves_vault` / `legacy_unit_serving` / `discover_local_units` seam (N3); new guided `automation.last_run_failed`, exit 75 is not a failure (N4); reinstall keeps recorded hooks and the repair passes a non-default `--units-dir` (N5); catalog patterns for the legacy-adopt failure and "Kept the existing schedule" (N6); quoted removal steps, no brace expansion (N7); liveness probed only when a job is recorded (N8); flow-log line corrected (N9); untracked files staged at commit (N10).
- Static gate after fixes: ruff clean; full pytest green except the known pre-existing demo-leak test, which passes after removing the leaked dirs.
- Next: commit-push.

## commit-push
- PR keyword: `Closes #359` — every requested change and acceptance criterion the issue owns is delivered, including the install guard the issue listed as related.
- Next: remote-gates (rebase, PR, CI). No further tracked flow-log entries after the PR opens.
