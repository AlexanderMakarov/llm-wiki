# Flow log — #146 harvest discard reason surface

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/146 (OPEN; labels: enhancement, self-heal)
- Title: Harvest re-proposes candidates you already discarded, and never reads the reason you recorded
- Owner re-scope (comment): #282 covered exact-name exclusion + merge-target reads from reason.txt; still open = free-text dismissal reason unused, and no surface when a close name reappears
- Route: no `bug` label → `/implement-feature`
- Next: resume-detection

## resume-detection
- Issue OPEN; no owning functional-spec; no open PR for remaining scope
- Roadmap still unchecked: "Harvest respects a dismissal (#146)"
- Allocated SPEC_NAME=`326-harvest-discard-reason-surface`
- Next: workspace

## workspace
- BRANCH=`feat/146-harvest-discard-reasons` from origin/main 143d000
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/feat-146-harvest-discard-reasons`
- TMP_VAULT=`$WT/.worktree-vault` + worktree config.json (absolute path)
- Next: specs (/awos:spec)

## specs — functional-spec
- Product choices: (1) propose near-matches but mark them; (2) name near-match only, reason for display
- Approved: `context/spec/326-harvest-discard-reason-surface/functional-spec.md`
- Next: `/awos:tech`

## specs — technical-considerations
- Approved (lgtm): dismissals.json SoT; no new reason.txt; dismissal_ledger sole I/O; near-match at list time; mockups + `(discarded without explanation)`
- Next: `/awos:tasks`

## specs — tasks
- Wrote `tasks.md`: 5 slices (ledger → CLI near-match → site → docs → regression)
- Agents: python-pro (impl), generalPurpose (docs), testing-expert unavailable → generalPurpose for Slice 5
- All slices Completed
- Next: verify + smoke confirm

## implement
- BRANCH=`feat/146-harvest-discard-reasons` WT absolute under `.claude/worktrees/`
- Delivered: dismissal_ledger, candidates rewrite, near_match, CLI+site, migrate dismissal-ledger, docs, acceptance tests
- Full gate: ruff clean; pytest tests/ exit 0
- Next: user smoke confirm (live vault — operator runs mutating commands)

## verify
- FR1–FR6 covered by tests/test_harvest_discard_reason_surface_acceptance.py + unit suites
- Live vault: backup + migrate dismissal-ledger + UX polish (multi prior list, name de-dupe, Discard with prior reason); operator smoke OK
- Next: local review

## local-review
- Smoke confirmed by operator
- review.md: Verdict Approve; Blockers 0; Nits 3
- Keep/drop: keep all — applied Nit1 agent-kit wiki-candidates.md; Nit3 JS comment; Nit2 stage untracked at commit
- Next: static gate → commit-push

## commit-push
- Issue link keyword: `Closes #146` — delivers remaining #146 scope (reason surface + near-match UX + dismissals.json rewrite); exact-name exclusion was #282
- Stage: product + tests + docs + context/spec/326 (exclude review.md)
- Next: push → PR → remote gates

## implement — Slice 2
- `list_candidates` → `attach_prior_dismissals`; CLI human line + `--json` prior_dismissal
- Near-match spellings: `FooBar`/`Foobar` fold equal (`norm_page_key`) — used `FooBars`/`Foobar` (ratio 0.9231) and `ApiClients`/`ApiClient` (empty reason)
- Vault verify list mockup green; focused pytest + ruff green; `.worktree-vault` cleaned
- Next: Slice 3 (candidates.html)

## implement — Slice 3
- Site payload + Name-cell Prior dismissal line; `(discarded without explanation)` for empty reason
- Next: Slice 4 (docs)

## implement — Slice 4 (docs / CHANGELOG / UPGRADING / context)
- User-visible delivery for #146: `dismissals.json` ledger (no new `*.reason.txt`), near-match marks on `candidates list` + `candidates.html`, `llmwiki migrate dismissal-ledger`, empty reason → `(discarded without explanation)`
- Docs: `docs/reference/cli.md`, `docs/reference/ui.md`, `CHANGELOG.md` [Unreleased] Added, `docs/UPGRADING.md` Unreleased note
- Product PR context: this flow-log entry + `notes.md` in this spec dir
- Next: Slice 5 (acceptance / regression)

## fix-bug #363 — fetch, diagnose, classify, fix (2026-10-23)
- Bug: [#363](https://github.com/AlexanderMakarov/llm-wiki/issues/363) — reading the dismissal ledger created `wiki/archive/candidates/dismissals.json` in a wiki that had no archive. A full test run therefore left a repo-root `wiki/` and `demo/wiki/archive/`, and the next run failed the self-contained-demo acceptance test.
- Branch `fix/363-ledger-read-no-write`, worktree `.claude/worktrees/fix-363-ledger-read-no-write`, throwaway vault `.worktree-vault/`.
- Root cause: `load_ledger` → `rebuild_ledger_from_archive` → `save_ledger` (`mkdir(parents=True)`) whenever `dismissals.json` was missing, archive or not. Reproduced with `tests/test_180_exclude_headless_acceptance.py::test_estimate_omits_marked_headless_from_both_adapters` (repo-root `wiki/`); a per-test probe on `origin/main` pinned the `demo/wiki/archive/` write to the same read path.
- Classification: **conformance** against this spec — auto-rebuild exists to import a legacy archive; creating an archive that never existed is a code over-reach. No functional-spec amendment.
- Fix: `load_ledger` returns an empty ledger without writing when `wiki/archive/candidates/` does not exist. `_ensure_dismissal_ledger` (candidates write path) now saves the ledger explicitly before archiving a stub, since it relied on the read's side effect.
- Regression test: `tests/test_dismissal_ledger.py::test_load_without_an_archive_writes_nothing` (red before the fix).
- Test convention (operator request): `tests/test_109_acceptance.py` → `tests/test_product_explains_itself_acceptance.py` (spec 008 slug); one-sentence behaviour docstrings; README-link and agent-kit scans fail on an empty input; the self-contained check names a stray repo-root `wiki/`. Dropped three duplicates covered by stronger tests (`serve` removal and `--local-root` in `test_static_site_no_server.py`, `--fail-on-errors` gate in `test_ci_workflow.py`, which absorbed the no-`--strict` assertion). Spec 008 docs point at the new path.
- Docs: the unreleased #146 CHANGELOG entry, `docs/UPGRADING.md` and `docs/reference/cli.md` say a vault with no archive reads as an empty ledger and is left untouched.
- Next: verify (two consecutive full runs in one checkout leave no stray dirs), smoke, local review.

## fix-bug #363 — verify (2026-10-24)
- Issue scenario replayed: two consecutive full `pytest tests/` runs in one checkout. Run 1: 6513 passed, 22 skipped, exit 0; run 2: 6513 passed, 22 skipped, exit 0. No `wiki/`, no `demo/wiki/archive/`, no untracked files after either run.
- The renamed acceptance module fails with a message naming the stray path when a repo-root `wiki/` exists (checked by creating one).
- Ledger-dependent modules (`test_dismissal_ledger`, `test_harvest_discard_reason_surface_acceptance`, `test_migrate_discarded_topic_links`, `test_candidates*`) pass, including the merge path that relied on the old write.
- Spec amendment: none (conformance).
- Next: operator smoke, local review.
- Smoke (operator asked the agent to run it, then confirmed): throwaway vault with `wiki/` but no `archive/`, `synth --estimate` — main checkout at `c9619eb` creates `wiki/archive/`; this worktree (same base + fix) creates nothing. A first smoke attempt was invalid (missing vault dir is refused before any ledger read; `candidates list` with no candidates never reads the ledger).

## fix-bug #363 — local review keep/drop (2026-10-24)
- Independent review (session-only `review.md`): **Approve** — 0 blockers, 2 nits. Operator kept both.
- N1: module docstring of `dismissal_ledger.py`, `load_ledger` / `iter_dismissals` / `iter_merges` and `migrate_dismissal_ledger.py` now say a read with no archive returns an empty ledger and writes nothing.
- N2: the operator-requested test-convention rewrite ships as its own `test:` commit in the same PR; the PR body lists it separately and names the modules covering the three dropped tests.

## fix-bug #363 — commit-push (2026-10-24)
- PR link keyword: `Closes #363` — the ledger read no longer writes, the test suite leaves no stray dirs (two consecutive runs), and the acceptance module is renamed with the clearer stray-path message: every expected item in the issue is delivered.
- Commits: `fix:` (ledger read, write-path save, regression test, docs, CHANGELOG, this flow log) then `test:` (acceptance module rename/rewrite, `test_ci_workflow` assertion, spec 008 path references).
- Next: rebase on `origin/main`, open PR, watch required checks. No further tracked-log writes after the PR opens.
