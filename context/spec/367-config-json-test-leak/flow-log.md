# Flow log — #367 test suite rewrites the checkout's config.json

## fix-bug #367 — fetch, diagnose, classify (2026-10-24)
- Bug: [#367](https://github.com/AlexanderMakarov/llm-wiki/issues/367) — a local `pytest tests/` run set `synthesis.backend` to `dummy` in the checkout's gitignored `config.json`; the scheduled job installed from that checkout then synthesized new sessions as placeholder pages.
- Branch `fix/367-config-json-test-leak`, worktree `.claude/worktrees/fix-367-config-json-test-leak`, throwaway vault `.worktree-vault/`.
- Spec: fix-as-spec directory (cross-cutting: `install-automation` / `configure-sources` config writes plus test isolation; no functional spec owns it). No functional-spec to amend.
- Reproduced: a per-test probe hashing the root `config.json` names one writer, `tests/test_automation_serves_vault_acceptance.py::test_incident_replay_doctor_names_the_schedule_and_the_repair_sticks` (doctor heal → in-process `install-automation --yes` with no `--synth-backend` → `load_synthesis_backend()` reads the isolated missing config → `dummy` → `_write_synth_backend` writes `REPO_ROOT/config.json`, which isolation does not redirect). The #91 guard missed it because `config.json` is gitignored.
- Classification: **conformance** — #91 / #142 already promise tests never write the developer's config.

## fix-bug #367 — fix, regression tests (2026-10-24)
- `config_schedule.user_config_path()` resolves the operator `config.json` at call time; `cli._write_synth_backend` and `configure_sources` (read and write) use it instead of `REPO_ROOT / "config.json"`, so the existing `_USER_CONFIG` redirect in `tests/conftest.py` covers writes too. Same file in production.
- Guard: `tests/tracked_files.py` also watches the gitignored root `config.json` (`OPERATOR_FILES`) and names it in the failure. Before the fix the guard failed the culprit test; after it the test passes and the file is untouched.
- Regression test `tests/test_tracked_file_guard.py::test_guard_fails_a_test_that_writes_the_operator_config` (red with `OPERATOR_FILES` emptied). The existing end-to-end guard test shares the new `_run_guarded_suite` helper.
- Tests that redirected the config by patching `REPO_ROOT` (`tests/test_configure_sources.py`, `_install_via_flags` in `tests/test_automation_install.py`) now patch `config_schedule._USER_CONFIG`.
- Docs: CHANGELOG *Fixed* entry; `docs/CODING_STANDARDS.md` Isolation rule.
- Next: full suite (no test may touch `config.json`), smoke, local review.

## fix-bug #367 — verify, smoke (2026-10-24)
- Full suite on the fix: 6516 passed, 22 skipped, exit 0; the root `config.json` is byte-identical before and after. (Stray `wiki/` / `demo/wiki/archive/` from the pre-#363 base disappear after rebasing onto the #363 merge.)
- Smoke (agent-run, operator confirmed): worktree `config.json` set to `"backend": "claude"`, then the culprit test — with `origin/main`'s four touched files it passes and leaves `"backend": "dummy"`; with the fix it passes and the file keeps `claude`.
- Next: local review.

## fix-bug #367 — local review keep/drop (2026-10-24)
- Independent review (session-only `review.md`): **Approve** — 0 blockers, 2 nits. Operator kept both and asked that the N1 test modules be rewritten to the repo's test conventions.
- N1: the "nothing written" assertions in the decline tests looked at `tmp_path/config.json` while the write now goes through `user_config_path()`. New `tests/checkout.py::redirect_checkout` points both the CLI checkout and the operator config at `tmp_path` and returns the config path; the decline tests assert on it. Each fails with a write injected at the start of `install-automation` (red-proof) and passes once the code is restored. `tests/test_configure_sources.py` uses the same helper.
- Conventions (operator request): `tests/test_156_acceptance.py` → `tests/test_automation_profiles_acceptance.py` (spec 010 slug); one-sentence behaviour docstring on every test in it and in `tests/test_automation_install.py` (88 added or shortened; rationale kept as comments); `test_escaping_leaves_ordinary_paths_byte_identical` deleted as an exact duplicate of the two byte-identical renderer tests; module docstring states its scope and specs.
- N2: rebase onto `origin/main` after the #363 merge, resolving the CHANGELOG *Fixed* ordering.

## fix-bug #367 — commit-push (2026-10-24)
- PR link keyword: `Closes #367` — writes go through the read path, the guard covers the root `config.json`, and a normal suite run leaves it untouched: every expected item in the issue is delivered.
- Commits: `fix:` (product change, guard, `tests/checkout.py`, configure-sources tests, the `_install_via_flags` redirect, docs, CHANGELOG, this flow log) then `test:` (decline assertions, acceptance-module rename, docstrings, duplicate removal).
- Next: rebase on `origin/main`, full suite, push, open PR, watch required checks. No further tracked-log writes after the PR opens.
