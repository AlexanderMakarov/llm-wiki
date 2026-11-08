# Flow log — #412 CHANGELOG skip ignores scoped titles

## 2026-11-08 — fetch, diagnose, classify, fix, regression test

- Bug: #412 (hit on #411, `chore(flow): …` title failed "CHANGELOG.md updated").
- Root cause: `.github/workflows/pr-lint.yml` classify step matched only unscoped globs (`chore:*`); the title job allows `(scope)`.
- Classification: conformance (workflow header says chore/docs/test skip the gate); no functional spec to amend.
- Fix: bash regex `^(docs|chore|test)(\([^\)]+\))?:`; title passed via `env: TITLE` instead of inline `${{ }}` in the script.
- Regression test: `tests/test_quality_gates.py::test_pr_lint_changelog_classify_skips_scoped_docs_chore_test` — RED on origin/main (2/6: scoped chore, scoped docs), GREEN on fix.
- Branch: `fix/412-changelog-skip-scoped-titles`. Next: local review.

## 2026-11-08 — local review, keep/drop, commit-push

- Local review: Approve, 0 blockers, 5 nits (session-only `review.md`, not committed).
- Keep/drop (operator): keep N1 (stage this log), N3 (drop no-op `.replace`), N4 (near-miss cases `tests: a`, `chore(): a` → no skip); drop N2, N5.
- Test now has 8 cases; RED on origin/main's workflow (bash rejects the inline `${{ }}`), GREEN on fix. Static gate green (ruff, full pytest).
- PR keyword: `Closes #412` — the issue's only expectation (scoped docs/chore/test skip; feat/fix still gated) is delivered.
