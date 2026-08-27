# Flow log — #149 candidates apply batch order

## fetch-bug — 2026-08-27
- BUG_ID: 149
- Title: candidates apply: a batch that merges into a peer it also promotes or discards is order-dependent
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/149
- State: OPEN; labels: bug; comments: none
- Symptom: `candidates apply` batch with merge targeting a peer that the same batch also promotes/discards/merges away is order-dependent; alphabetical table order can change outcome; no validation
- Suggested fix (issue): refuse conflicting batch before execution, or define dependency order and document it
- Linked: found while rebuilding candidates review for #109; roadmap lists "Batch apply is order-independent (#149)"
- Next: resume-detection

## resume-detection — 2026-08-27
- Not already fixed (issue open; no merged PR for this fix)
- No pre-existing owning functional-spec for batch-order independence; 008 mentions apply shape but not this AC
- SPEC_NAME: `149-candidates-apply-batch-order` (orphan fix-as-spec)
- Next: workspace

## workspace — 2026-08-27
- Dirty primary tree: untracked `candidates.png`, `candidates-top.png` (warn only; not AWOS leftovers)
- BRANCH: `fix/149-candidates-apply-batch-order`
- WT: `.claude/worktrees/fix-149-candidates-apply-batch-order` (from origin/main @ 051cf24)
- TMP_VAULT: `$WT/.worktree-vault` + worktree `config.json` isolating vault
- Next: diagnose

## diagnose — 2026-08-27
- Repro: merge+discard both orders — page order succeeds both; reverse fails merge (target gone). promote+merge both exit 0 but different target resolution paths.
- Root cause: `llmwiki/candidates_site.py:apply_candidate_actions` — sequential apply, no cross-action conflict check; page order = alphabetical `list_candidates`.
- Fix shape: `validate_candidate_batch` before mutate; refuse if merge `into` is promote/flip-promote/discard/merge slug elsewhere in batch; CLI exit 2; docs/cli.md line.
- Related tests: `tests/test_candidates_site.py` (no conflict coverage yet).
- Confidence: high
- Next: classify

## classify — 2026-08-27
- Verdict: orphan — product intent on roadmap ("Batch apply is order-independent (#149)"); no pre-existing functional-spec AC for this rule. Spec 008 covers apply shape / review UX, not batch conflict.
- Action: fix code + regression test; **no functional-spec to amend** (skip amend-spec). Document refuse rule in reference CLI docs + CHANGELOG.
- Chosen behavior: refuse whole conflicting batch (issue preferred over dependency reordering).
- SPEC_NAME: `149-candidates-apply-batch-order`
- Next: fix

## fix — 2026-08-27
- Added `validate_candidate_batch` in `candidates_site.py`; called at start of `apply_candidate_actions` before any mutation.
- CLI `candidates apply` catches `ValueError`, prints conflict, exit 2.
- Docs: `docs/reference/cli.md` one line; CHANGELOG under Unreleased Fixed.

## fix — 2026-08-27
- `validate_candidate_batch` in `llmwiki/candidates_site.py`; called from `apply_candidate_actions` before mutate
- CLI `ValueError` → stderr `error: batch conflict: …`, exit 2
- Docs: `docs/reference/cli.md`; CHANGELOG Unreleased Fixed #149
- Next: regression-test

## regression-test — 2026-08-27
- Updated `test_the_assembled_batch_is_what_apply_executes` (non-conflicting merge target)
- Added conflict refuse / zero-mutate / CLI exit 2 / positive control tests in `tests/test_candidates_site.py`
- pytest that file: 34 passed
- Next: verify-criteria

## verify-criteria — 2026-08-27
- Criteria checked against TMP_VAULT (evidence in orchestrator verify run): refuse merge+promote / merge+discard conflicts with exit 2 and no mutations; non-conflicting merge+promote applies.
- Smoke confirm: pending user
- Next: smoke confirm → local-review (after confirm)

## smoke confirm — 2026-08-27
- Operator asked orchestrator to probe live vault; conflict refuse on real pending entities/concepts (exit 2, pending set identical before/after).
- Next: local-review

## local-review — 2026-08-27
- Review file: `context/spec/149-candidates-apply-batch-order/review.md` (session-only, not for commit)
- Verdict: Request changes — Blockers 1 · Nits 4
- Next: keep/drop with operator

## keep/drop — 2026-08-27
- Operator: fix all (blocker + nits 2–4; nit 1 = commit)
- Applied: static-site test Canonical merge; `_BATCH_PEER_ACTIONS = _VALID_ACTIONS`; Raises docstring flip-promote; JS `collectActions` conflict guard + unit test
- Gates: ruff clean; pytest 4544 passed, 48 skipped
- Next: commit-push

## commit-push — 2026-08-27
- Committing product + flow-log; review.md session-only (gitignored)
- Branch: fix/149-candidates-apply-batch-order
- After push: open PR (no further flow-log appends)
