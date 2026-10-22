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
