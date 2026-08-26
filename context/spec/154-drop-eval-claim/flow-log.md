# Flow log — 154-drop-eval-claim

## fetch-bug
- Issue #154 open: `llmwiki eval` missing; docs/CI claimed it shipped.
- Decision (operator): **Drop the claim** (not build eval).
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/154

## resume-detection
- Not closed; no merged PR for #154.
- SPEC_NAME: `154-drop-eval-claim` (orphan fix-as-spec).
- Next: workspace

## workspace
- BRANCH: `fix/154-drop-eval-claim`
- WT: `.claude/worktrees/fix-154-drop-eval-claim`
- TMP_VAULT: `$WT/.worktree-vault`
- Base: origin/main @ a1af607
- Primary checkout dirty (untracked screenshots + `context/spec/163-estimate-done-predicate/`) — warned, not a blocker.
- Next: diagnose

## diagnose
- Repro: `python3 -m llmwiki eval` → invalid choice exit 2; no llmwiki/eval.py
- Must-fix: docs/reference/slash-commands.md; docs/feature-matrix.md I4; context/product/roadmap.md #154 item
- Leave: historical CHANGELOG v0.3; demo/raw mirrors; spec 008 notes; test_ci_workflow guard
- Next: classify

## classify
- Verdict: **Divergence (orphan)** — docs advertised capability with no code; no owning functional-spec to amend
- SPEC_NAME remains `154-drop-eval-claim`; "no functional-spec to amend"
- Operator chose Drop; structural quality stays on `llmwiki lint`
- Next: fix

## fix
- Dropped live eval claims in slash-commands, feature-matrix I4, roadmap #154 done, DECLINED entry, CHANGELOG Unreleased, UPGRADING clarify, test_v03 docstring
- Next: regression-test

## regression-test
- Added `tests/test_v03.py::test_eval_framework_never_shipped_docs_stay_honest`
- pytest test_v03 + test_ci_workflow green
- Next: verify-criteria

## verify-criteria
- Checked: no `llmwiki eval` in slash-commands; I4 declined+#154; CLI lacks eval; lint on TMP_VAULT runs
- amend-spec: skipped (orphan, no functional-spec)
- Next: smoke confirm (user)

## smoke-confirm
- Operator confirmed drop looks right (2026-08-26).
- Next: local-review

## local-review
- Operator: keep-all; fix all findings.
- Blocker: moved `build_parser` import to module top in `tests/test_v03.py` (PLC0415).
- Nit 1: demo/raw slash-commands, upgrade-guide, feature-matrix I4 — no live `llmwiki eval` claims.
- Nit 2: broadened `test_eval_framework_never_shipped_docs_stay_honest` (UPGRADING + demo mirror asserts).

## commit-push
- Preparing conventional commit for #154 drop-eval-claim (docs + regression + demo honesty).
- review.md session-only — not staged.
- Next: push then open PR (stop appending flow-log after PR opens).
