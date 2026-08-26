# Fix log — #163 `synth --estimate` done predicate vs synth state+mtime

Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/163

## fetch-bug
Fetched issue #163 (OPEN, label `bug`, no comments). Sibling of #161 (merged via PR #167). Symptom: `synth --estimate` treats a source as done when its pages exist on disk (`output_exists`), while the real `synth` run skips only when state has a fresh-enough mtime entry and the page is not pending. Disagreement whenever disk and state disagree (restored pages / cleared state; interrupted multi-part docs). Acceptance: estimate and run share one done predicate, with tests pinning both directions. Linked: #161. No attachments.

## resume-detection
Issue OPEN; no merged PR for #163; no prior `context/spec/163-*` flow log. Fresh start. SPEC_NAME=`163-estimate-done-predicate` (orphan fix-as-spec; no owning functional-spec for the done predicate — adjacent: 001 honest estimate candidates, 006 honest synthesized counts, 009 one-call synth, 161 estimate doc part paths).

## workspace
Branch `fix/163-estimate-done-predicate`, worktree `.claude/worktrees/fix-163-estimate-done-predicate` off `origin/main` @ f20d1db. Throwaway vault at `.worktree-vault` with worktree-local `config.json`; live vault untouched. Dirty primary tree (untracked screenshots; other worktrees) noted, not a blocker.

## diagnose
Diagnosed in worktree against throwaway vault.
- Estimate “done”: `llmwiki/synth/estimate.py` `synthesize_estimate_report` — sessions ~405–412 (`output_exists` / `discovered_source_keys`); docs ~467–470 (`output_exists` via `source_page_paths`).
- Run “skip”: `llmwiki/synth/pipeline.py` `synthesize_new_sessions` ~1570–1576 (`rel in state` + mtime + not force + not page_is_pending).
- No shared done-predicate helper. Shared pieces: `source_page_paths` (#161), stub/topics pending helpers.
- Repro Case 1 (docs): estimate `Already synthesized: 2 of 2` / `New since last run: 0` vs `synth --docs-only --sources-only` → `Scanned 1, new 1` after clearing state with a real non-stub page on disk. Dummy pages alone mask as stubs.
- Proposed fix: extract run skip into shared helper both call; drop estimate `output_exists` as done.

## classify
**Conformance bug — no owning spec for the done predicate.** Spec 001 covers Candidates labelling; spec 006 covers Corpus/Already-synthesized *units* and explicitly scoped out changing backlog-vs-done math for that feature (not a permanent product lock on disk-as-done); spec 009/145 cover interrupt Home counts; #161 covered which pages a source owns. The implied invariant is estimate prices what the next run processes — code violates that. No `functional-spec.md` to amend; `amend-spec` skipped. SPEC_NAME stays `163-estimate-done-predicate`.

Behavior note (not a divergence amendment): state-less vaults with pages on disk will start pricing as new (same as the run) — intentional per the issue.

Next: fix (delegated), then regression test.

## fix
Shared `source_synth_is_done(rel, state, mtime, *, force=False, page_is_pending=False)` in `pipeline.py` (next to `source_page_paths`). Run skip loop calls it; estimate sessions+docs loops call it (lazy import). Dropped `output_exists` / `discovered_source_keys` as done paths. `state_keys` now accepts `{rel: mtime}` map (or bare set → +inf for tests). Callers (`cli`, `discover_unsynth_session_rels`, `refresh_synth_pending`) pass full state. CHANGELOG Fixed bullet. ruff clean. No commit.

## regression-test
Added `tests/test_source_synth_is_done.py` (10 tests: predicate unit + estimate directions). Updated stub_backlog / #161 / migrate / AC232 fixtures that still asserted disk-as-done. RED: temporarily OR`d `output_exists` into estimate matched → `test_estimate_real_page_without_state_is_not_synthesized` failed; restored fix; 10/10 green. ruff clean on touched tests.

## verify-criteria
Driven on throwaway vault via CLI (dummy backend + hand-written real page).

- **A (real page + fresh state mtime):** estimate `Already synthesized: 1 of 1` / `New since last run: 0`; run `Scanned 1, new 0` — agree done.
- **B (same page, state cleared):** estimate `Already synthesized: 0 of 1` / `docs 1 new`; run `Scanned 1, new 1` (protected real page under dummy) — agree not done / would process.
- Shared helper `source_synth_is_done` used by both paths; unit+estimate tests pin both directions (RED-validated).

Pre-fix behaviour for B was estimate Already N via `output_exists` while run treated as new — fixed.

Next: smoke confirm with user (live-vault read-only / operator-pasted mutating commands), then local review.

## smoke-confirm
User asked orchestrator to run live-vault checks. Read-only `--estimate --vault` on live vault + dry_run synthesize (sessions). Pre-fix (origin/main) vs post-fix: Already synthesized 80→73, New 1367→1374 (docs 231 unchanged); disk-only gap = 7 sessions (6 no state, 1 stale mtime). Dry-run `new_files=1143` matches estimate; 0 wiki pages mutated. User said continue → local review.

## local-review

## apply-findings
N1+N2 applied (no commit): dropped unused `synthesized_source_keys` from `synthesize_estimate_report` and product/test call sites that only fed it; kept `discover_synth_source_keys` for #24/#37. Added UPGRADING Unreleased subsection for #163; CHANGELOG Fixed bullet notes the kwarg removal for test callers.

## commit-push
N1+N2 applied (drop dead `synthesized_source_keys` from estimate API/callers; UPGRADING Unreleased note for estimate/state behaviour flip). Local review verdict Comment, 0 blockers / 2 nits (both fixed). Classification: conformance, no functional-spec amend. Next after this commit: rebase onto origin/main, push, open PR, watch CI. Stop appending to this log once the PR is open.
