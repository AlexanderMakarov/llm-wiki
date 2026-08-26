# Flow log — #138 remove /vs/ surface

## fetch-bug
- BUG_ID: 138
- Title: render_vs_section has no production callers and hardcodes REPO_ROOT/wiki — the /vs/ model-comparison surface never renders
- Decision (operator): **remove** the /vs/ model-comparison surface from everywhere (not wire it). Catalog `/models/` out of scope unless tightly coupled and only used by /vs/.
- Next: resume-detection → workspace → diagnose

## resume-detection
- Issue open; no merged fix PR for #138
- SPEC_NAME: `138-remove-vs-surface` (orphan fix-as-spec; no pre-existing owning functional-spec)
- Next: workspace

## workspace
- BRANCH: `fix/138-remove-vs-surface`
- WT: `.claude/worktrees/fix-138-remove-vs-surface`
- TMP_VAULT: `.worktree-vault` (isolated config.json)
- Base: origin/main @ cefb89e
- Next: diagnose

## diagnose
- Reproduction: `build_site` never calls `render_vs_section`; `site/vs/` never emitted
- Root cause: advertised surface never wired; dead `compare.py` + `render_vs_section` + docs
- Keep `/models/` / schema / models_page; remove vs-only module and claims
- Next: classify

## classify
- Verdict: **Divergence / intentional product cut** — docs claimed `/vs/`; removing dead surface + claims. No pre-existing owning `functional-spec.md` to amend → skip amend-spec; update DECLINED + product docs + CHANGELOG as part of the fix.
- SPEC_NAME: `138-remove-vs-surface`
- Next: fix

## fix
- Deleted `llmwiki/compare.py`, `tests/test_compare.py`
- `build.py`: dropped compare imports + `render_vs_section`; left `render_models_section`
- Stripped vs-only tests (`test_page_kinds`, `test_post_review_remediation`, `test_edge_cases_unit`); dropped Compare from `test_reference_coverage`
- `render/css.py`: removed `.vs-*` block; nav comment no longer lists Compare
- `.github/workflows/e2e.yml`, `.github/CODEOWNERS`: dropped `compare.py` paths
- Docs: ui / reader-api / getting-started / architecture / setup-guide / UPGRADING + matching `demo/raw/docs/*`; CHANGELOG Unreleased Removed #138; roadmap #138 done; DECLINED cut entry + revised comparison/`/vs/` survivors
- Next: verify (ruff + pytest)

## verify
- ruff: clean
- pytest: green except pre-existing `test_add_doc.py::test_thin_page_without_renderer_warns` (trafilatura env; unrelated to #138)
- Next: (no commit/push per operator)

## verify-criteria / smoke
- Operator asked agent to run live-vault build; EXIT 0
- 1853 HTML files; **no `site/vs/`**
- Index has no Compare /vs/ nav links
- Next: local-review → commit-push → PR → merge (operator: proceed with merging)


## local-review
- Verdict: Approve; Blockers 0; Nits 1 (UPGRADING Unreleased #138 note)
- Review file: context/spec/138-remove-vs-surface/review.md (session-only, not committed)
- Applied N1: docs/UPGRADING.md + demo upgrade-guide-01 mirror
- Next: commit-push

## commit-push
- Staging all #138 removal + flow-log; excluding review.md / .worktree-vault / config.json
- Last flow-log write before PR open
