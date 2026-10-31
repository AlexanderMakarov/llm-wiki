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
