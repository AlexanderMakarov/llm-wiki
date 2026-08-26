# Flow log — #142 test config isolation

## fetch-bug
- BUG_ID: 142
- Title: tests read the developer's gitignored config.json, so local settings can fail the suite
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/142
- State: open; no dedicated fix PR; labels: bug
- Symptom: suite merges repo-root gitignored `config.json`; local synthesis settings fail `tests/test_synth_parallel_acceptance.py` (`test_start_line_precedes_first_page_line_over_the_cli`, `test_all_with_synth_honours_config_concurrency_with_no_flag_to_set_it`)
- Suggested fix (issue): neutralize root `config.json` suite-wide in `tests/conftest.py`; opt-in for merge tests
- Linked: found during #109 gates; related merged PRs #144/#155 are not this fix
- Next: resume-detection

## resume-detection
- Issue open; no merged PR for this fix
- No prior flow-log; allocating orphan fix-as-spec `142-test-config-isolation` (#164)
- Next: workspace

## workspace
- BRANCH: `fix/142-test-config-isolation`
- WT: `.claude/worktrees/fix-142-test-config-isolation`
- TMP_VAULT: `$WT/.worktree-vault`
- Primary checkout dirty (untracked images + `context/spec/163-estimate-done-predicate/`) — warned, not blocking
- Note: `./setup.sh` lacked +x in worktree; ran via `bash ./setup.sh`
- Next: diagnose

## diagnose
- Reproduced: poison synthesis.concurrency=4 → 2 fail (`test_start_line_precedes_first_page_line_over_the_cli`, `test_all_with_synth_honours_config_concurrency_with_no_flag_to_set_it`); isolation config restored
- Root cause: `llmwiki/config_schedule.py` `_load_sessions_config()` merges `_USER_CONFIG` (repo-root `config.json`); `synthesize_new_sessions` pulls concurrency from that when unset
- Autouse `_isolate_default_vault` only stubs vault path, not full user config
- Next: classify

## classify
- Verdict: orphan / conformance to intended suite isolation — product merge of `config.json` is correct; tests must not inherit developer settings
- SPEC_NAME: `142-test-config-isolation`
- no functional-spec to amend
- Next: fix

## fix
- Autouse in `tests/conftest.py`: neutralize `_USER_CONFIG` + `convert.USER_CONFIG_FILE` (missing path); keep vault stub
- Retarget `test_all_with_synth_honours_config_concurrency_with_no_flag_to_set_it` patch → `synth_pipeline._load_sessions_config`
- Notes: `notes.md` (isolation contract); CHANGELOG Unreleased Fixed; one-line CONTRIBUTING Testing
- Next: verify (poison config + related sanity)

## verify
- Poison `synthesis.concurrency=4` → `tests/test_synth_parallel_acceptance.py` 20 passed
- Sanity: `test_source_checkout_guard` + `test_config_vault_default` + `test_exclude_headless` 48 passed
- Isolation `config.json` restored to WT `.worktree-vault`
- Next: (later stage) regression test / PR

## fix
- Autouse in `tests/conftest.py` redirects `_USER_CONFIG` + `USER_CONFIG_FILE` away from root `config.json`
- Retargeted acceptance concurrency patch to `synth_pipeline._load_sessions_config`
- Docs: CHANGELOG Fixed, CONTRIBUTING Testing one-liner, `notes.md`
- Poison acceptance: 20 passed; sanity 48 passed
- Open risk: subprocess CLI still sees real root config (out of issue's conftest scope)
- Next: regression-test

## regression-test
- Added `tests/test_suite_config_isolation.py::test_repo_root_config_json_does_not_poison_sessions_config`
- 21 passed with acceptance suite slice
- Next: verify-criteria

## verify-criteria
- Touched criteria (issue reproduce): with poison concurrency=4, previously-failing acceptance tests + regression → green (orchestrator re-check)
- Awaiting user smoke confirm before local-review

## verify-criteria (evidence)
- Poison concurrency=4 + `test_suite_config_isolation` + full `test_synth_parallel_acceptance` → green
- Regression restore path fixed to snapshot/restore prior config.json (no hardcoded vault)
- Smoke confirm: waiting on user

## verify-criteria / smoke
- Operator asked orchestrator to self-check
- Poison concurrency=4: 21 passed (isolation + synth parallel acceptance)
- Related opt-in suites: 48 passed
- Fixed ruff I001 on regression test imports
- Treating smoke as confirmed → local-review

## local-review
- Review file: `context/spec/142-test-config-isolation/review.md` (session-only, not to commit)
- Verdict: Request changes — Blockers: 1, Nits: 0
- B1: regression writes REPO_ROOT/config.json — awaiting keep/drop

## local-review (keep/drop)
- Kept B1 → option 1 (assert `_USER_CONFIG` binding; no repo-root writes)
- Applied; 21 passed; review.md remains session-only / untracked via gitignore
- Next: commit-push

## commit-push
- Staging fix + context notes/flow-log; excluding review.md, config.json, .worktree-vault
- Conventional commit referencing #142; push branch; then open PR (remote-gates)
