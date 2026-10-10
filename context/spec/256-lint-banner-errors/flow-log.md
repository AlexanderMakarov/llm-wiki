# Flow log — #256 lint banner errors-first

## fetch-bug
- BUG_ID: 256
- Title: fix(ui): Home lint banner should surface errors, not alphabetically-first warnings
- Labels: bug, self-heal
- Symptom: `format_lint_error_for_ops` truncates console report from first alphabetical `## rule` section; warnings (e.g. content_freshness) appear in Home banner while errors that tripped `--lint-fail errors` sit later and are invisible.
- Related: #234 (owning Home lint note / ops.last_lint_error)
- Next: resume-detection → workspace → diagnose

## resume-detection
- Issue OPEN; no merged PR for #256
- Owning behavior: context/spec/234-home-timeline-automation-stamps (R2)
- SPEC_NAME for this run: 256-lint-banner-errors (fix-as-spec); amend 234 on divergence if needed
- Next: workspace

## workspace
- BRANCH: fix/256-lint-banner-errors
- WT: (this worktree)
- TMP_VAULT: .worktree-vault
- Next: diagnose

## diagnose
- Repro: mix of early-alphabet warnings + late-alphabet errors; `--lint-fail errors`; banner shows warnings only
- Root cause: `state_store.format_lint_error_for_ops` truncates from first `##` in alphabetically-ordered `lint/report.render_text` output; fail policy never consulted
- Fix shape: `render_ops_error(outcome, …, fail_on=…)` structured errors-first; wire `cmd_lint` / `_run_lint_step`; keep ~6-line budget
- Next: classify

## classify
- Verdict: **Divergence**
- Owning spec: `234-home-timeline-automation-stamps` R2 (+ technical-considerations) currently require console-truncated / reuse render_text; amend to policy-failing findings first, console line shape retained
- Fix-as-spec log/review: `256-lint-banner-errors`
- Next: fix

## fix
- `llmwiki/lint/report.py` — new `render_ops_error(outcome, total_pages, *, fail_on, max_lines=6)` (in `__all__`); `render_text` now shares `_summary_lines` / `_rule_sections` with it (console output unchanged)
- `llmwiki/cli.py` (`cmd_lint`) and `llmwiki/pipeline.py` (`_run_lint_step`) — store `render_ops_error` text on policy failure (`fail_on_warnings` / `lint_fail == "warnings"` → `"warnings"`, else `"errors"`)
- `llmwiki/state_store.py` — docstrings: `format_lint_error_for_ops` only enforces the line budget; selection happens before it
- `tests/test_lint_ops_error_render.py` — renderer unit tests + `cmd_lint` and `_run_lint_step` regressions (both fail on pre-fix code)
- Spec amendment (Divergence): `context/spec/234-home-timeline-automation-stamps/functional-spec.md` R2 + decisions row, `technical-considerations.md` §2 lint text; dated Change Log in both
- Docs: `CHANGELOG.md` Unreleased › Fixed; `docs/reference/ui.md`; `docs/reference/state-persistence.md`
- Next: review

## regression-test
- Added tests/test_lint_ops_error_render.py (6 tests): unit render_ops_error + cmd_lint + pipeline wiring
- Critical case fails on old HEAD files, passes on fix
- Next: verify-criteria

## verify-criteria
- AC1 (--lint-fail errors, mix): ops note has summary + error rule, not early warnings — evidenced by test_lint_ops_error_render + inline renderer demo
- AC2 (ok): record_lint_ops(failed=False) clears last_lint_error — covered by existing test_234_ops_stamps
- AC3 (truncation): max_lines + … — covered by tight max_lines=2 test
- Spec 234 R2 amended (divergence)
- Next: user smoke confirm (live vault paste commands), then local-review

## verify-criteria / smoke
- Live vault: 0 errors → banner empty (AC2); no visual failure case
- Synthetic demo: injected render_ops_error note; Home showed page_findability [error], not content_freshness warnings — user confirmed 2026-10-10
- Next: local-review

## local-review-apply
- N1: `render_ops_error(outcome, total_pages, *, fail_on)` returns the full policy-selected note (no `max_lines`); `state_store.format_lint_error_for_ops` is a pass-through (CRLF / trailing blank lines only)
- N1: Home JS (`renderStateWidget`) shows the red `.state-lint-banner` only when `ops.last_lint_error` has an `[error]` finding line, displaying 10 lines + `…`; new **Linter output** `detailsSection` right after Estimate warnings renders `ops.last_lint_report` pre-wrap ("No linter output." when empty); `.state-lint-report` CSS, banner `max-height` scroll removed
- N1: `ops.last_lint_report` added to state defaults / `_ensure_shape`; `record_lint_ops(report_text=…)` stores it on failure, clears it with `last_lint_error` on success; `cmd_lint` and `_run_lint_step` pass the full `render_text` report
- Tests: `tests/test_lint_ops_error_render.py` (no Python truncation, stored note > 10 lines, `last_lint_report` on failure); `tests/test_234_ops_stamps.py` truncation tests replaced by pass-through / full-storage tests; `tests/test_state_widget.py` asserts the `[error]` gate, 10-line display limit, and Linter output placement
- B1: reverted tracked `demo/llmwiki-state.*` churn; removed scratch backup and old smoke folders; smoke site rebuilt from a copy of `demo/` under gitignored `.worktree-vault/lint-banner-smoke/` (11 errors + 10 warnings injected)
- N2: rebased onto `origin/main`; one conflict in `docs/reference/ui.md` (upstream #311 wording kept, lint sentence rewritten)
- Docs: CHANGELOG #256 bullet, `docs/reference/ui.md`, `docs/reference/state-persistence.md`; spec 234 R2, decisions row, technical-considerations, Change Log rewritten for the new design
- Next: smoke confirm in browser, then commit-push

## local-review-2-apply
- Kept N1: rewrote spec 234 R2 rules + ACs (10-line / error-gated red note; warnings-only AC)
- Kept N2 as (a): warnings-only → no red banner; Timeline + Linter output; CHANGELOG/ui/docs + widget test
- Next: refresh smoke vault, user confirm, then commit-push

## commit-push
- Issue link keyword: **Closes #256** — delivers all acceptance criteria the issue owns (errors-first Home note, truncation, clean ok path) plus operator-requested Linter output collapsible / 10-line JS budget / warnings-only signalling documented in amended #234 R2
- Classification: Divergence (spec 234 R2 amended)
- Local review: review.md Request changes (applied); review-2.md Comment (N1+N2a applied); smoke confirmed on .worktree-vault/lint-banner-smoke
- Next: push, open PR, remote gates (stop appending tracked flow-log after PR open)
