# Flow log — #160 demo case collision

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/160 (OPEN, bug)
- Symptom: `demo/wiki/candidates/entities/LLMWiki.md` and `llmwiki.md` both tracked; case-insensitive checkouts never clean
- Proposed: delete one path; CI guard `git ls-files | tr 'A-Z' 'a-z' | sort | uniq -d`; optional generator normalize (out of scope / own issue)
- Next: resume-detection

## resume-detection
- Issue OPEN; no merged PR for #160; collision still on origin/main
- No owning functional-spec; allocated fix-as-spec `160-demo-case-collision`
- Next: workspace

## workspace
- BRANCH=`fix/160-demo-case-collision`
- WT=`.claude/worktrees/fix-160-demo-case-collision`
- TMP_VAULT=`$WT/.worktree-vault` + worktree `config.json`
- Primary checkout warning: was on unrelated branch with dirty tree — work isolated in WT
- Next: diagnose

## diagnose
- Reproduced: YES — `git ls-files | tr … | uniq -d` → `demo/wiki/candidates/entities/llmwiki.md`
- Root cause: `llmwiki/candidates_harvest.py` writes stub from exact wikilink spelling (no case fold); demo snapshot committed both
- KEEP: `demo/wiki/candidates/entities/llmwiki.md` (37 sources; dominant `[[llmwiki]]`)
- DELETE: `demo/wiki/candidates/entities/LLMWiki.md` (+ index bullet ~line 131)
- CI: `.github/workflows/ci.yml` job `lint-and-test` new step after working-tree-clean
- Generator normalize OUT OF SCOPE (caveat: refresh_demo can reintroduce; guard catches)
- Next: classify

## classify
- Verdict: **orphan / no functional-spec to amend** (fix-as-spec `160-demo-case-collision`)
- Not conformance-to-existing-AWOS-spec; not divergence requiring amendment of a functional-spec.md
- Acceptance = issue #160 proposed fix items 1+2
- Next: fix

## fix
- Deleted `demo/wiki/candidates/entities/LLMWiki.md`; kept `llmwiki.md`
- Updated `demo/wiki/index.md` Candidates (10)→(9), dropped LLMWiki bullet
- CI step in `.github/workflows/ci.yml` lint-and-test: Case-insensitive path collisions
- CHANGELOG Unreleased Fixed #160
- No candidates_harvest.py change (OOS)
- Next: regression-test

## regression-test
- Added `tests/test_case_insensitive_paths.py::test_no_git_tracked_paths_collide_when_case_folded`
- Local run: PASS; origin/main still has the collision (RED evidence)
- Next: verify-criteria + smoke confirm

## verify-criteria
- Self-checked (operator asked agent to verify): collision empty; only llmwiki.md tracked; index Candidates (9); CI step present; CHANGELOG #160; pytest regression PASS
- Smoke: self-confirm per operator "check yourself"
- amend-spec: skipped (orphan / no functional-spec)
- Next: local-review

## local-review
- Verdict: Request changes (1 Blocker, 4 Nits) → applied B1, N1, N2, N3; N4 = staging discipline for commit-push
- Review file session-only (gitignored): `context/spec/160-demo-case-collision/review.md`
- Follow-up filed: #204 (harvest case-colliding stubs); CHANGELOG cites it
- Next: commit-push

## commit-push
- Staging: demo deletion, index, ci.yml, CHANGELOG, test, flow-log — NOT review.md
- Conventional commit referencing #160
- After this entry: stop writing tracked flow-log (PR opens next)
