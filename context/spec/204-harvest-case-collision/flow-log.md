# Flow log — #204 harvest case-colliding stubs

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/204 (OPEN, bug+important)
- Symptom: `candidates_harvest.py` writes stubs with exact wikilink spelling (no case fold); pending `llmwiki.md` does not suppress later `LLMWiki` — case-insensitive FS collision; refresh_demo can reintroduce after #160 guard
- Related: #160 (demo+CI guard, closed via PR #205); generator normalize was OOS there
- Expected: skip or merge targets whose `_norm_slug` already matches an existing candidate stub (prefer higher refs / dominant spelling)
- Next: resume-detection

## resume-detection
- Issue OPEN; no merged PR for #204 harvest runtime fix (PR #205 was #160 demo cleanup only)
- No owning functional-spec for harvest case-fold; allocated fix-as-spec `204-harvest-case-collision`
- Related notes only in `160-demo-case-collision/flow-log.md` (filed #204 as follow-up)
- Next: workspace

## workspace
- BRANCH=`fix/204-harvest-case-collision`
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/fix-204-harvest-case-collision` (absolute; §10 #213)
- TMP_VAULT=`$WT/.worktree-vault` + worktree `config.json` (absolute path)
- Primary checkout: main behind origin/main by 6 — work isolated in WT from origin/main
- Note: first recipe used relative WT and nested vault under `$WT/.claude/worktrees/...`; corrected per §10
- Next: diagnose

## diagnose
- Reproduced: YES — 3× `[[llmwiki]]` + 3× `[[LLMWiki]]` → two HarvestedTargets, write_stubs emits both entities/{LLMWiki,llmwiki}.md; pending stub not in resolved
- Root cause: `count_source_refs` exact keys; `harvest_targets` no same-norm fold among targets; `write_stubs`/`_existing_subdir` exact filename only
- Proposed fix: fold by `_norm_slug` in harvest_targets (union sources, dominant spelling by refs); `_existing_subdir`+write path match pending by norm so alternate case refreshes stub
- Do NOT add candidates/ into resolved (would break evidence refresh)
- Confidence 95
- Next: classify

## classify
- Verdict: **orphan / no functional-spec to amend** (fix-as-spec `204-harvest-case-collision`)
- No pre-existing functional-spec for harvest case-fold; #160 was demo+CI only
- Acceptance = issue #204 expected behavior (no two stubs that fold to same path)
- Next: fix

## fix
- Paths: `llmwiki/candidates_harvest.py` (`harvest_targets` fold by `_norm_slug`; `_existing_stub` + `write_stubs` reuse pending filename; `_topic_records_for_target` matches by norm); `CHANGELOG.md`; `docs/reference/page-kinds.md`; this flow-log
- Local repro: TMP_VAULT under `$WT/.worktree-vault` — 3× `[[llmwiki]]` + 3× `[[LLMWiki]]` → one HarvestedTarget + one stub file
- Next: testing-expert regression test

## regression-test
- Added `test_case_colliding_wikilink_spellings_fold_to_one_candidate` in `tests/test_candidates_harvest.py` (#204): 3× `llmwiki` + 3× `LLMWiki` → one harvest target; pre-seeded `llmwiki.md` refreshed, no sibling `LLMWiki.md`
- `python3 -m pytest tests/test_candidates_harvest.py -q` — 38 passed
- Next: code-reviewer / PR

## verify-criteria
- Criteria checked (issue #204 acceptance):
  1. Harvest does not emit two stubs that fold to the same path — PASS (one target LLMWiki refs=6; entity_files=['llmwiki.md'] only)
  2. Pending stub refreshed by norm slug (pre-seed llmwiki.md + mixed case harvest) — PASS (write_stubs refreshed llmwiki.md, no LLMWiki.md sibling)
  3. Regression test green — PASS (`test_case_colliding_wikilink_spellings_fold_to_one_candidate`)
- amend-spec: skipped (orphan / no functional-spec)
- Next: smoke confirm (user) then local-review

## verify-criteria / smoke
- Self-checked (operator: "check yourself"): TMP_VAULT CLI `synth --candidates-only` + API reuse path; harvest suite + case-insensitive path tests PASS; no case-folded duplicate candidate filenames
- amend-spec: skipped (orphan / no functional-spec)
- Next: local-review

## local-review
- Verdict: Request changes → applied B1+N1
- B1: restored `## [2.3.0] — 2026-09-08` after Unreleased `### Removed`; Unreleased Fixed keeps only the #204 bullet (+ release-note)
- N1: `assert targets[0].name == "LLMWiki"` in `test_case_colliding_wikilink_spellings_fold_to_one_candidate`
- `review.md` is session-only (not committed)
- Gates: `ruff check llmwiki tests scripts` pass; `pytest tests/test_candidates_harvest.py -q` pass
- Next: re-review / PR update

## commit-push
- Staging: candidates_harvest.py, test_candidates_harvest.py, CHANGELOG, page-kinds.md, flow-log — NOT review.md / config.json / .worktree-vault
- Conventional commit referencing #204
- After this entry: stop writing tracked flow-log (PR opens next)
