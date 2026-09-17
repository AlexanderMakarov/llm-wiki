# Flow log — #270 ci: align default-branch workflow triggers with main

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/270 (OPEN, bug)
- Title: ci: align default-branch workflow triggers with main
- Symptom: release-drafter.yml, cross-browser.yml, agents-e2e.yml push triggers still use `master`; default branch is `main`
- Acceptance: change those three to `main`; keep PR/workflow_dispatch; add regression test derived from documented default branch
- Next: resume-detection

## resume-detection
- Not closed; no merged PR for this fix
- No pre-existing owning functional-spec → orphan fix-as-spec `270-ci-default-branch-triggers`
- Next: workspace

## workspace
- BRANCH=`fix/270-ci-default-branch-triggers`
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/fix-270-ci-default-branch-triggers`
- TMP_VAULT=`…/fix-270-ci-default-branch-triggers/.worktree-vault` (absolute; nested relative vault removed per §10 #213)
- Next: diagnose

## diagnose
- Reproduced: yes — origin/HEAD→main; three workflows on.push.branches = master only
- Root cause: stale default-branch-only push triggers in release-drafter.yml, cross-browser.yml, agents-e2e.yml
- Fix shape: change those three to main; keep PR/dispatch; regression test patterned on workflow YAML tests; derive expected branch from CONTRIBUTING/RELEASE_PROCESS (and optionally origin/HEAD)
- Out of scope: ci.yml, e2e.yml, gitleaks.yml (intentional dual master+main)
- Next: classify

## classify
- Verdict: orphan **conformance** (align triggers with documented default; no owning functional-spec to amend)
- SPEC_NAME=`270-ci-default-branch-triggers`
- Next: fix

## fix
- Set `on.push.branches` to `main` in release-drafter.yml, cross-browser.yml, agents-e2e.yml; left ci/e2e/gitleaks dual-branch lists alone
- Regression: `tests/test_270_default_branch_workflow_triggers.py` derives expected branch from CONTRIBUTING.md + RELEASE_PROCESS.md
- Docs: CHANGELOG Fixed; playwright-agents-bootstrap example branch list; context flow-log (this note)
- Next: verify

## regression-test
- Added/kept `tests/test_270_default_branch_workflow_triggers.py`; RED confirmed (master-only release-drafter fails assertion); GREEN on fix
- Next: verify-criteria

## verify-criteria
- AC: three workflows push on main — confirmed via file read + test
- AC: PR path filters / workflow_dispatch unchanged — confirmed via diff (only branches line)
- AC: dual-branch workflows untouched — confirmed
- AC: regression test exists and RED/GREEN — confirmed
- AC: ruff + focused pytest green — confirmed
- Classification: conformance → skip amend-spec
- Next: smoke confirm (user)

## smoke-confirm
- Operator: check yourself and proceed (2026-09-17)
- Re-ran: branch triggers + ruff + focused pytest — green
- Next: local-review

## commit-push
- Staging workflows + test + CHANGELOG + maintainers doc + flow-log; excluding review.md
- Commit message: fix(ci): align default-branch workflow triggers with main (#270)
- Next: remote-gates (stop appending flow-log after PR opens)
