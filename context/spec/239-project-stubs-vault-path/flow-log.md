# Flow log — #239 project stubs vault path

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/239
- Title: sync auto-build seeds wiki/projects stubs into the git clone instead of the vault
- State: OPEN; labels: bug, important; comments: none
- Symptom: `build_site(..., seed_project_stubs=True)` writes stubs via `PROJECTS_META_DIR = REPO_ROOT / "wiki" / "projects"` instead of vault `wiki/projects/`; also reads profiles from clone
- Expected: stub writes + profile reads use `wiki_dir / "projects"`
- Next: resume-detection

## resume-detection
- Not closed; no merged/open PR for #239
- No pre-existing owning functional-spec for vault-aware PROJECTS_META_DIR
- SPEC_NAME: `239-project-stubs-vault-path` (fix-as-spec, #164)
- Next: workspace

## workspace
- BRANCH: `fix/239-project-stubs-vault-path`
- WT: `.claude/worktrees/fix-239-project-stubs-vault-path`
- TMP_VAULT: `$WT/.worktree-vault` + worktree `config.json` isolating from live vault
- Base: `origin/main` @ eb14a80
- Primary checkout was dirty/other-branch; worktree isolated — OK
- Next: diagnose

## diagnose
- Reproduced: `python3 -m llmwiki build --vault .worktree-vault --seed-project-stubs` with session `project: fix239-test` created `$WT/wiki/projects/fix239-test.md`; vault `wiki/projects/` unchanged (`.gitkeep` only); site correctly under vault
- Root cause: `llmwiki/build.py:185` `PROJECTS_META_DIR = REPO_ROOT / "wiki" / "projects"`; write at `build_site:3096`; reads at `render_project_page:1640-1641`, `render_analytics:2097`
- Fix shape: `projects_meta_dir = wiki_dir / "projects"` in `build_site`; thread into stub seed + profile/topics reads
- Next: classify

## classify
- Verdict: **conformance** (vault `wiki_dir` already correct for other build I/O; constant ignores it)
- SPEC_NAME: `239-project-stubs-vault-path` (orphan fix-as-spec)
- No pre-existing `functional-spec.md` to amend — skip amend-spec
- Next: fix

## fix
- `build_site`: `projects_meta_dir = wiki_dir / "projects"`; stub seed + `render_project_page` use it; `render_analytics` derives from `wiki_dir`
- `PROJECTS_META_DIR` kept as default for tests that monkeypatch the constant
- Files: `llmwiki/build.py`, `CHANGELOG.md`
- Next: regression-test

## regression-test
- `tests/test_project_stubs.py::test_build_site_seed_stubs_writes_vault_not_repo` — PASS (27/27 file)
- Asserts vault stub exists and unique slug not under `REPO_ROOT/wiki/projects/`
- Next: verify-criteria

## verify-criteria
- AC write: `build --vault $TMP_VAULT --seed-project-stubs` seeded `fix239-seed-new.md` under vault only; no `$WT/wiki`
- AC read: hand profile description "Vault profile for #239 verify" rendered in `site/projects/fix239-verify.html`
- Regression pytest green
- Classification: conformance — skip amend-spec
- Next: smoke-confirm (paused for user)

## smoke-confirm
- User initially rejected smoke while viewing session layout (#229) + subagent-on-site expectation (product gap under `only-raw`); clarified those are out of #239 scope
- User chose proceed with **#239 only** (finish vault-path fix)
- #239 evidence still holds: live build seeded vault `wiki/projects/` only; no clone-root `wiki/` on primary or worktree
- Next: local-review

## local-review
- Verdict: Request changes (2 Meta blockers = uncommitted work; 3 nits)
- User: keep all nits; blockers resolved by commit-push
- Applied nits 3–5: vault profile read regression test, `render_project_page` docstring for `projects_meta_dir`, `render_analytics` threads `projects_meta_dir` from `build_site`
- review.md session-only — not staged (#159)
- Next: commit-push

## commit-push
- Commit code + CHANGELOG + flow-log; exclude review.md / vault / config.json
- Push BRANCH; open PR — stop appending this log after PR opens
