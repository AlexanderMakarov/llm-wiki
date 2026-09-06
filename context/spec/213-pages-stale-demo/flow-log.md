# Flow log — #213 pages stale demo

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/213 (OPEN)
- Title: demo site is four releases stale (v1.5.0 live vs v2.1.0 released) — Pages never republishes
- Labels: bug, important
- Symptom: live Pages serves manifest version 1.5.0; package is 2.1.0; pages.yml is workflow_dispatch-only
- Ordering note: owner wants manual republish after #210/#211/#212; #210 MERGED (PR #219); #211/#212 still OPEN
- Next: resume-detection → workspace

## resume-detection
- No merged PR for #213; no existing owning spec; allocated SPEC_NAME=213-pages-stale-demo
- Next: workspace

## workspace
- BRANCH=fix/213-pages-stale-demo
- WT=.claude/worktrees/fix-213-pages-stale-demo (absolute under repo)
- TMP_VAULT=$WT/.worktree-vault (absolute path in config.json)
- Primary checkout dirty (unrelated); worktree from origin/main
- Next: diagnose

## diagnose
- Reproduced: live manifest 1.5.0 (2026-08-15); __version__ 2.1.0; manifest.py stamps package version at build
- Root cause: .github/workflows/pages.yml `on:` is workflow_dispatch-only (#69) — no tag republish
- Aggravators: no post-deploy version assert; no scheduled live-vs-__version__ freshness check (synthetic.yml also dispatch-only)
- Fix shape: tag trigger v*.*.* + keep dispatch; post-deploy curl assert; scripts/check_live_version.py + scheduled pages-freshness.yml; update deploy/uptime/RELEASE docs; static YAML tests like test_release_pipeline.py
- Flow defect hit: relative WT path after `cd "$WT"` nested vault — fixed with absolute TMP_VAULT this run; recorded in delivery-flow §10
- Next: classify

## classify
- Verdict: **divergence** — docs/deploy/github-pages.md documents dispatch-only as design (#69); #213 intentionally changes to tag-triggered publish
- SPEC_NAME=213-pages-stale-demo (orphan fix-as-spec); no pre-existing functional-spec to amend — skip inventing functional-spec.md; behavior change lands in docs/deploy + CHANGELOG
- Manual deploy AC deferred until #211/#212 (owner ordering); #210 already merged
- Next: fix

## fix
- `pages.yml`: added `push: tags: ["v*.*.*"]` (mirrors `release.yml`), kept `workflow_dispatch`; header comment now says tag + dispatch republish (#213) while push-to-main stays off (#69)
- `pages.yml` deploy job: after `actions/deploy-pages`, checkout + Python 3.12 + `scripts/check_live_version.py --url "$PAGE_URL" --attempts 6 --delay 15`; `page_url` passed via env (no `${{ }}` interpolation into the shell)
- Deviation from issue text: asserts against checked-out `__version__`, not `${GITHUB_REF_NAME#v}` — one identical assertion for tag and dispatch runs, and a tag pushed without the version bump fails instead of publishing a mislabelled site
- New `scripts/check_live_version.py` (stdlib only): pure `manifest_url` / `parse_manifest_version` / `versions_match` / `normalise_version` / `package_version` helpers, importable for tests; `--url` fetch with retries or `--manifest-json` (file / `-` stdin) for offline use; exits 0 match, 1 mismatch, 2 unreachable, 3 malformed. Reads `__version__` textually from `llmwiki/__init__.py` so no workflow needs `pip install markdown`
- New `.github/workflows/pages-freshness.yml`: `cron: "0 6 * * 1"` (Mon 06:00 UTC) + dispatch, checkout + Python, runs the checker against the fork's live demo manifest URL, no deps installed
- Docs: `docs/deploy/github-pages.md` (banner, Step 4 two triggers + self-verify, troubleshooting: trigger shapes + new stale-after-deploy section), `docs/uptime.md` (version-freshness section, exit-code table, `/manifest.json` row), `docs/maintainers/RELEASE_PROCESS.md` (Pages verify now expected, not optional), `CHANGELOG.md` two Fixed bullets under Unreleased
- Verified offline: all four exit paths + `--expected v1.5.0` tag form + stdin + URL normalisation exercised against local fixtures; `ruff check` clean; no live deploy run (deferred per #211/#212)
- CONTRIBUTING context gate satisfied by this file (`.github/workflows/` + `docs/maintainers/` touched)
- Next: regression-test stage — static YAML assertions in the style of `tests/test_release_pipeline.py` (tag trigger present, dispatch kept, post-deploy assert wired, freshness cron/URL) + unit tests for the pure helpers

## regression-test
- New `tests/test_pages_deploy.py` (31 test functions → 54 cases with parametrization); tokens `@layer: unit` / `@spec: 213-pages-stale-demo` / `@regression` in the module docstring, `REPO_ROOT` from `llmwiki` per `tests/test_release_pipeline.py`
- Static half — `pages.yml`: `v*.*.*` tag trigger present, `workflow_dispatch` retained, no `branches:` in the trigger block (#69 stays deliberate), deploy job runs the checker **after** `actions/deploy-pages` (index-ordered assert — a check placed above the deploy would read the previous deploy and pass on the stale site), `page_url` reaches the checker via `env:` with no `${{ }}` in the run line, `--attempts` retries present
- Static half — `pages-freshness.yml`: `schedule:` + a `cron:` expression, dispatch available, asserts the fork's own manifest URL and that no other fork's Pages host appears, runs `scripts/check_live_version.py`, and stays read-only (no `deploy-pages` / `upload-pages-artifact` / `pages: write`)
- Unit half — `scripts/check_live_version.py` loaded by path via `importlib` (script, not a package): `normalise_version` / `versions_match` (tag prefix + whitespace, plus a negative set led by the live-1.5.0-vs-tree-2.1.0 reproduction), `manifest_url` (site root with/without trailing slash, manifest link, empty → `ValueError`), `parse_manifest_version` (happy + 8 malformed payloads incl. the Pages 404 HTML that returns 200), `package_version()` against `llmwiki.__version__` and against a synthetic tree
- CLI half — all four exit codes offline through `--manifest-json`: 0 fresh (and `--expected v1.5.0` tag form), `EXIT_MISMATCH` stale with both versions and `213` in stderr, `EXIT_MALFORMED` on HTML and on a version-less manifest, `EXIT_UNREACHABLE` on a missing file, stdin `-` path, `SystemExit` on a bare invocation, distinct exit-code values
- RED validated against pre-fix `HEAD` without running it: `git show HEAD:.github/workflows/pages.yml` matches none of `tags:` / `v*.*.*` / `check_live_version.py` / `--attempts`, and both `pages-freshness.yml` and `scripts/check_live_version.py` are absent — so 29 of 31 fail pre-fix. The two that would already pass (`keeps_workflow_dispatch`, `does_not_deploy_on_every_main_push`) are deliberate retention guards for the #69/#213 decisions, not new-behavior tests
- Green: `ruff check tests/test_pages_deploy.py` clean; `python3 -m pytest tests/test_pages_deploy.py -q` → 54 passed; re-run alongside `tests/test_release_pipeline.py` + `tests/test_ci_workflow.py` → 98 passed (no cross-talk, no tracked file touched)
- No production code, workflow, or doc edited in this stage; nothing committed or pushed

## verify-criteria
- AC1 pages.yml deploys on version tags — PASS (YAML `push.tags: v*.*.*` + regression tests)
- AC4 post-deploy version assert — PASS (deploy job runs check_live_version after deploy-pages; offline stale→exit 1 / fresh→exit 0; B1 retry-on-stale applied)
- AC5 scheduled freshness check — PASS (pages-freshness.yml weekly cron + checker)
- AC2 live site serves current release — PENDING (live still 1.5.0; needs manual/tag deploy)
- AC3 manual deploy after doc fixes — DEFERRED (#211/#212 still OPEN; #210 merged)
- amend-spec: divergence recorded; no pre-existing functional-spec — docs/CHANGELOG already updated in fix stage; skip inventing functional-spec.md
- User: run local checks yourself; continue review + PR
- Local smoke: ruff clean; pytest test_pages_deploy 57 passed; live check exit 1 on 1.5.0 (expected)
- Next: local-review keep/drop → commit-push

## local-review
- Independent review (inherit code-reviewer): Request changes — 1 Blocker, 1 Nit → file context/spec/213-pages-stale-demo/review.md (session-only, not committed)
- B1 applied: check_url retries fetch→parse→compare on mismatch/malformed for --url; --manifest-json stays single-shot
- N1 applied: urlopen monkeypatch tests (stale→fresh, always-stale, HTML→fresh)
- Verdict after fixes: ready to commit (operator asked to continue to PR)
- Next: commit-push

## commit-push
- Staging path-aware #213 files + flow-log + delivery-flow §10; excluding review.md, config.json, .worktree-vault
- Conventional commit referencing #213; then push BRANCH and open PR
- After PR open: stop appending this tracked flow-log

## local-review
- B1+N1 applied: `--url` now retries fetch→parse→compare (mismatch + ManifestError + fetch); `--manifest-json` stays single-shot; monkeypatched urlopen tests for stale→fresh / all-stale / HTML→fresh
- Review findings file is session-only (not committed)
