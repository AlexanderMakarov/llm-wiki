# Local checklist review — 003-awos-context-ci-gate (#117)

- **Branch:** `feat/117-awos-context-ci-gate`
- **Stage:** PRE-PUSH local review (no PR exists yet; CI has not run)
- **Reviewed against:** `docs/maintainers/REVIEW_CHECKLIST.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/DECLINED.md`, `CONTRIBUTING.md`, `SECURITY.md`
- **Scope reviewed:** `git diff origin/main...HEAD` (4 spec files) **plus** all unstaged/untracked project files (`.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/pr-lint.yml`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/maintainers/REVIEW_CHECKLIST.md`, `tests/test_pr_template.py`, `tests/awos_context_gate.py`, `tests/test_awos_context_gate.py`, `tests/test_awos_context_gate_acceptance.py`). `.worktree-vault/` excluded from content review but see Blocker 2.
- **Verdict:** **request-changes** — 2 blockers, 4 major, 9 nits

---

## Verification I ran locally

| Check | Result |
|---|---|
| `ruff check llmwiki tests scripts` | clean |
| `python3 -m pytest tests/ -q` (full suite) | all pass, 0 failures, ~78s |
| Targeted: gate unit + acceptance + PR template | 117 tests pass |
| Gate CLI, armed path only, throwaway repo | exit 1, five `::error::` lines |
| Gate CLI, armed path + `context/` file | exit 0, silent |
| Gate CLI, deletion of an armed file only | exit 1 (deletions arm the gate — correct) |
| FR5 honesty: branch touches only `docs/tutorials/`, base branch advanced with an `llmwiki/` commit | merge-base base → exit 0; tip-to-tip base → exit 1. The workflow's `git merge-base` step is load-bearing and correct. |
| Gate CLI with an unreachable SHA | uncaught `CalledProcessError` traceback (see Major 4) |
| `actions/checkout@v7` pin | matches every other workflow in `.github/workflows/` — not a finding |
| `from tests.awos_context_gate import …` | resolves; `tests/__init__.py` exists, and `tests/tracked_files.py` is existing precedent for a non-`test_` helper module in `tests/` |
| PR template box count | 17 boxes; `test_contributing_documents_the_checklist_box_count` derives the number from the template and passes against CONTRIBUTING's "17-box" heading |

Checklist sections that are clean: no new runtime deps (no `pyproject.toml` change); Layer-0 untouched; no rendering/HTML change so no XSS surface; no network calls; no telemetry; no server binding change; no new CLI subcommand / config key / lint rule, so no `docs/reference/*` row is owed; `CHANGELOG.md` has an Unreleased entry; the armed-prefix constant matches the functional spec exactly; `DECLINED.md` contains nothing that conflicts with this gate; one concern per PR.

---

## Blockers

### B1. The implementation is not committed — pushing now produces a spec-only PR

`git diff origin/main...HEAD` contains **only** the four `context/spec/003-awos-context-ci-gate/*.md` files. Everything that implements #117 — the gate module, both test files, the `awos-context` workflow job, and all four documentation surfaces — is sitting in the working tree as modified/untracked:

```
 M .github/PULL_REQUEST_TEMPLATE.md
 M .github/workflows/pr-lint.yml
 M CHANGELOG.md
 M CONTRIBUTING.md
 M docs/maintainers/REVIEW_CHECKLIST.md
 M tests/test_pr_template.py
?? tests/awos_context_gate.py
?? tests/test_awos_context_gate.py
?? tests/test_awos_context_gate_acceptance.py
```

Pushed as-is, the PR ships specs claiming `Status: Completed` with every acceptance criterion `[x]` and no gate. It would also pass its own gate for the wrong reason (only `context/` changed, so nothing arms it). Commit all nine files — GPG-signed, atomic, per CONTRIBUTING — before pushing, then re-verify `git diff origin/main...HEAD --stat` lists them.

### B2. `.worktree-vault/` is untracked **and not gitignored** — a `git add -A` commits local vault content

`git check-ignore -v .worktree-vault` reports NOT IGNORED, and `git status --porcelain -uall .worktree-vault` lists 14 untracked files under `.worktree-vault/wiki/` (`MEMORY.md`, `SOUL.md`, `CRITICAL_FACTS.md`, `dashboard.md`, …). The repo's `wiki/` ignore patterns are root-anchored, so they don't reach this nested copy.

That matters right now because B1's natural fix is `git add -A` to pick up the three untracked test files — which would also stage the vault. That directly violates CONTRIBUTING Privacy rules #2 and #3 and ARCHITECTURE "What must NEVER land in a PR" (`wiki/` pages other than allow-listed seeds, user-local state). Fix both halves: stage the test files explicitly by path, **and** add `.worktree-vault/` to `.gitignore` so the trap doesn't survive this session. Then confirm `git status --porcelain -uall` shows nothing under `.worktree-vault/` as staged.

---

## Major

### M4. The gate's real entry point has no test coverage

`main()` and `git_changed_paths()` — the two functions CI actually executes — are never called by either test file. The tests cover the pure predicates thoroughly (117 assertions), but FR5 "honest branch comparison" is verified only by asserting the literal string `git merge-base` appears in `pr-lint.yml`, and FR2's exit code is verified only via `gate_passes(...) is False`. Nothing proves the script exits 1, or that the merge-base wiring produces the right file set.

I built that test by hand to review this: a `tmp_path` repo, `git init`, a fork point, one branch commit touching `docs/tutorials/`, one base-branch commit touching `llmwiki/`, then `main(["--base", mb, "--head", head])`. It passes with the merge-base and fails tip-to-tip, which is exactly the regression worth locking in — the tech spec calls tip-to-tip diffing out as the quirk being avoided. Please add it (and a `SystemExit`/return-code assertion for the armed-without-context case) rather than leaving the CI-facing path untested.

### M5. An unreachable or invalid SHA produces a Python traceback, not a gate message

`git_changed_paths()` passes `check=True`, so any `git diff` failure raises `CalledProcessError` out of `main()`:

```
subprocess.CalledProcessError: Command '['git', 'diff', '--name-only', 'deadbeef', '2985c8e…']' returned non-zero exit status 128.
```

Exit status is 1, so the gate fails closed — correct — but the log is indistinguishable from a real "you forgot your notes" failure, and a contributor reading it will go looking for a missing `context/` file that isn't the problem. This is reachable in practice on shallow or partially fetched checkouts and on unusual fork-PR ref states. Catch `CalledProcessError`, emit one `::error::` line naming the diff that failed ("could not diff `<base>`..`<head>`; the gate cannot judge this PR"), and keep the non-zero exit.

### M6. The "hard fail" promise depends on a branch-protection change that nothing records

FR2 says the check fails the PR, and the job is named `AWOS context updated` specifically so it can be a required check — the tech spec's risk section flags it as "operational note for maintainers / PR body." But nothing in this diff records it: `CONTRIBUTING.md` § Branch protection still lists only "CI must pass before merge / signed commits / up-to-date branch", and there is no ops note anywhere in `context/`. Until the check is added to branch protection, a red `awos-context` job warns but does not block the merge button, so the gate is advisory. Add the check name to `CONTRIBUTING.md` § Branch protection (alongside the other required checks) and call out the one-time repo-settings step in the PR body.

### M7. Confirm `::error::` annotations render from stderr

`print_failure()` writes to `sys.stderr`, while the sibling `changelog` job in the same workflow echoes its `::error::` lines to stdout. If the runner does not parse workflow commands off stderr in this context, FR2's "the log shows a full explanation" silently degrades to plain unannotated log text, and the tests would not catch it — they assert on the `::error::` prefix in an in-memory buffer, not on rendered annotations. I did not want to guess at runner behavior here: either verify it on this PR's first live run and note the evidence, or default `stream` to `sys.stdout` for consistency with the neighboring job. Either resolution is fine; leaving it unverified is what I'm flagging.

---

## Nits

- **N8. Missing type hint on a new public function.** `print_failure(stream=None)` — every other function in the module is annotated. Suggest `stream: TextIO | None = None`.
- **N9. Test name understates the assertion.** `test_review_checklist_lists_at_least_one_armed_prefix` asserts `len(matched) >= 3`. Rename to match what it checks.
- **N10. Over-constrained source assertion.** `test_gate_module_source_contains_no_label_logic` asserts the substring `label` never appears in `tests/awos_context_gate.py`, which forbids even a comment explaining *why* there is no label bypass — the most useful comment that module could carry. Assert on concrete label names (`awos-exempt`, `skip-awos`) or on behavior instead.
- **N11. Whole-file doc assertions can pass on unrelated prose.** `test_contributing_rule_mentions_no_label_escape` checks `"no label" in text` across all of `CONTRIBUTING.md`; same pattern for the checklist file. Anchor them to the AWOS line (e.g. the bullet containing `context/`) so a future unrelated sentence can't keep them green after the rule is deleted.
- **N12. Heavy overlap between the two test files.** The acceptance file re-parametrizes predicates the unit file already covers; the docstring explains the layering, which I accept, but ~117 assertions against ~40 lines of pure logic is a lot of surface to keep in sync. Consider folding the unit file into the acceptance one.
- **N13. Drift guards are asymmetric.** `CONTRIBUTING.md` is asserted to list all six armed prefixes, `REVIEW_CHECKLIST.md` only three, and the PR template none — yet "docs must list the same set in prose" is the named drift risk in technical-considerations §3. Assert the full set on each prose surface.
- **N14. Mixed wrap style in `REVIEW_CHECKLIST.md`.** The new Meta bullet is one long line; every neighboring bullet is hard-wrapped at ~65 columns. The repo's markdown rule favors the new line, so this is fine — flagging only so it's a deliberate choice rather than an accident.
- **N15. `flow-log.md` records local workspace bookkeeping.** The worktree directory and throwaway vault directory are named in a committed file. Both are repo-relative with no username or home path, so the privacy rule is satisfied; it's still machine-session detail living in the permanent record.
- **N16. Say why the gate module lives in `tests/`.** It's deliberate (recorded in flow-log: `scripts/` is an exempt path, so a gate under `scripts/` would not arm itself), and `tests/tracked_files.py` is precedent. A one-line note in the module docstring would stop the next reader from "fixing" the location.

---

## Open items that cannot be checked pre-push

- **CI green** — REVIEW_CHECKLIST Meta requires lint-and-test (3.12), performance-budget, and the privacy scan to pass on the pushed head SHA. Per CONTRIBUTING § After you push, watch the run and report before calling this ready.
- **First live run of the new job** — confirms both the merge-base wiring against a real PR payload and M7 (annotation rendering).
- **Build/runtime smoke** — N/A for this change; nothing in the diff touches the converter, builder, or viewer.
