# Flow log — #210 pypi-install-docs

## fetch-bug / resume-detection / workspace
- BUG_ID: 210
- SPEC_NAME: 210-pypi-install-docs (orphan fix-as-spec)
- Branch: fix/210-pypi-install-docs
- Worktree: .claude/worktrees/fix-210-pypi-install-docs
- Entry: issue OPEN, no merged PR; #213 postponed per operator
- Next: diagnose

## diagnose / classify
- Reproduced: pypi.org/pypi/llm-wiki/json → 404; llmwiki (Hosuke) blocks similarity; docs/action install llm-notebook
- Root cause: soft-skip publish gate + wrong dist name in docs/action; pyproject was llm-wiki (unpublishable vs similarity)
- Decision: distribution name **llm-wiki-plus** (operator-created pending publisher); CLI/module stay llmwiki
- Classification: orphan fix-as-spec — no functional-spec to amend
- Next: fix + regression-test

## workspace (owner setup)
- Created GitHub environment `release`
- Set vars.PYPI_PUBLISHING=true
- Operator: confirm PyPI pending publisher = Project llm-wiki-plus · Owner AlexanderMakarov · Repo llm-wiki · Workflow release.yml · Env release

## fix

### Packaging identity
- `pyproject.toml` name → `llm-wiki-plus`. Import + CLI stay `llmwiki`.
- `llmwiki/install_hint.py` `DIST_NAME` → `llm-wiki-plus` (this is the runtime source of every optional-extra hint, so it matters more than any doc line).

### Release health
- `release.yml`: header rewritten around the real name rationale (`llmwiki` taken by another author; `llm-wiki` rejected by PyPI similarity). Publish gate `vars.PYPI_PUBLISHING == 'true'` kept, with its comment reframed — the variable is set, so a skip now means releases were switched off, not "not configured yet".
- New `smoke` job, `needs: publish`, no `continue-on-error`: venv → `pip install "llm-wiki-plus==${TAG#v}"` from real PyPI (5 attempts, 30s apart, for CDN propagation) → assert `llmwiki --version` matches the tag. Version compare strips non-alphanumerics and compares against `llmwiki<version>`, so it works for `2.1.0` and `2.1.0rc1` alike.
- `github-release` keeps `if: always()`; a failed `smoke` is what turns the run red.

### Two blocking bugs found while proving the action works
Both were discovered by installing the wheel into a clean venv rather than reading code, and both had to be fixed for an action-smoke job to be possible at all.

1. **`model_pricing.csv` was not in the wheel.** `llmwiki/cache.py` read it from `Path(__file__).parent.parent`, i.e. the repo root, which is outside the distribution. An installed copy therefore loaded an empty pricing table and every `sync`/`build` aborted with `ValueError: unknown model/family 'sonnet'` from the synth estimate. Fixed by moving the file to `llmwiki/model_pricing.csv`, adding it to `[tool.setuptools.package-data]`, and having `MODEL_PRICING_CSV` prefer the packaged copy with the old repo-root path as fallback. **This is arguably a separate concern from #210 and the operator may want it split into its own PR** — flagged rather than hidden.
2. **The composite action wrote outside the caller's checkout.** Bare `llmwiki init`/`sync`/`build` resolve an unnamed vault to `REPO_ROOT` = the directory above the installed package = `site-packages`, not the cwd. The action's `site-dir` output (`$(pwd)/site`) pointed at a directory that never existed. Fixed with `--vault .` on all three steps in both `action.yml` and `.github/workflows/llmwiki-action.yml`.

### action-smoke design (sync *was* the fragile part)
- Verified: `llmwiki sync` exits **1** when no adapter has a session store, so a bare runner cannot get past the action's sync step.
- Chosen: **seed rather than skip.** The CI job copies `tests/fixtures/claude_code/minimal.jsonl` into `$HOME/.claude/projects/action-smoke/` before invoking the action, so sync has a real store and the whole action — install, init, sync, build — is exercised. Preferred over dropping sync or teaching the action to tolerate an empty sync, because a no-op sync would not have caught bug 1 above.
- Rejected alternative: checking the repo out under a subdirectory to dodge the `.llmwiki-source-checkout` guard. Unnecessary — the guard tests `REPO_ROOT` (the installed package's parent), and `pip install .` lands in site-packages, so it never fires.
- Job asserts `site/index.html` and `site/style.css` exist. `package: .` installs the checkout, per the locked decision.
- Verified locally end to end: `git archive HEAD` → clean venv → `pip install .` → seeded fixture → `init/sync/build --vault .` → 11 HTML files, exit 0 on every step.

### Docs
- Switched to `llm-wiki-plus`: `README.md`, `CLAUDE.md` (install + upgrade line), `AGENTS.md`, `docs/tutorials/01-installation.md`, `docs/UPGRADING.md` (install lines + the v1.2.0 "distribution name" rationale), `docs/reference/cli.md` (install mention + three `[graph]` extras), `docs/cheatsheet.md`, `docs/feature-matrix.md` E7, `docs/maintainers/RELEASE_PROCESS.md`, `llmwiki/graphify_bridge.py`, `llmwiki/cli.py`, `llmwiki/pipeline.py`, `llmwiki/agent_kit/{commands/wiki-all.md,skills/wiki-all/SKILL.md}`.
- `docs/deploy/pypi-publishing.md` rewritten: name rationale as a two-row table, `llm-wiki-plus` / `AlexanderMakarov` throughout, the `smoke` job in the pipeline description, and troubleshooting entries for similarity rejection and both smoke failure modes.
- `RELEASE_PROCESS.md`: a skipped publish is explicitly no longer normal.
- History left alone: `CHANGELOG.md` entries, `context/`, `demo/raw/docs/**`. `RELEASE-NOTES-v1.2.0.md` got a one-line superseded note at the top and nothing else.

### Tests
- New `tests/test_install_docs_match_packaging.py`: parses `[project] name` with `tomllib`, walks `git ls-files` for `*.md`/`*.yml`/`*.yaml` outside the `demo/` · `context/` · `CHANGELOG.md` · `RELEASE-NOTES*` allowlist, and requires every `pip install` of an `llm-*` distribution to use exactly that name. Also guards that the scan is non-vacuous, that the four primary entry points still carry an install line, and that `llm-notebook` is never offered as an install.
- `tests/test_release_pipeline.py`: kept the gate assertion; added a `_job_block` helper and five smoke-job assertions (exists, `needs: publish`, installs `<pyproject name>==`, asserts `llmwiki --version`, no `continue-on-error` key). Added three doc assertions tying the walkthrough's project-name row to `pyproject.toml` and requiring the similarity rationale and the smoke job to be documented.
- Updated name expectations in `tests/test_v03.py`, `tests/test_156_acceptance.py`, `tests/test_automation_install.py`.

## regression-test / verify-criteria (partial)
- Offline AC covered: install-docs↔packaging test green; release.yml smoke job assertions green; dist name llm-wiki-plus throughout live docs
- Live AC (`pip install llm-wiki-plus` succeeds / version matches tag) deferred until first post-merge tag
- Next: operator smoke confirm + keep model_pricing in-PR decision → local-review → commit-push

## amend-spec
- Skipped — no functional-spec to amend (orphan fix-as-spec)
- Operator: keep model_pricing.csv packaging + action `--vault .` in this #210 PR

## verify-criteria / smoke-confirm
- Waiting on operator smoke confirm (offline AC). Live pip AC after first tag post-merge.

## verify-criteria / smoke-confirm
- Operator asked agent to run optional check; green in worktree (install-docs + release-pipeline + ruff)
- Next: local-review

## local-review
- Applied N1–N7 + N9; kept N8 (UPGRADING's historical sections naming `llm-wiki-plus` are intentional).
- N1 `release.yml`: `normalise()` helper applied to *both* sides of the version compare (strip non-alphanumerics, lowercase).
- N2 `release.yml`: `smoke` is now `needs: [build, publish]` with `if: always() && needs.build.result == 'success'` plus a first step that hard-fails on any `publish` result other than `success`. `build` had to join `needs` because the `needs` context only carries direct dependencies — with `needs: publish` alone, `needs.build.result` is empty and the job would skip on every tag. Three new assertions in `tests/test_release_pipeline.py` (runs on `if: always()`, `build` in `needs`, fail-when-publish-not-success); the existing `needs: publish` assertion now parses the `needs:` list. CHANGELOG / `pypi-publishing.md` / `RELEASE_PROCESS.md` wording split into the two mechanisms (gate-off skip → precondition failure; broken-but-published → install assertion).
- N3 `action.yml`: `package` passed through `env: PACKAGE`; `additional-args` through `env: ADDITIONAL_ARGS`, read into a bash array so it word-splits without being glob-expanded or interpolated into the command line.
- N4 `install_hint.py`: historical sentence no longer names the distribution.
- N5: new `install_hint.pip_install_command(extra)` built from `DIST_NAME`; `cli.py` (`_BUILDER_QUESTION`, graph-builder warning) and `pipeline.py` (graphify fallback hint) render through it, `graphify_bridge.py`'s docstring points at it instead of repeating the name. New test ties the rendered hint to `pyproject.toml`'s `[project] name`.
- N6 `docs/tutorials/01-installation.md`: PyPI is Step 2 and recommended (upstream `#246` gate and "until then clone is authoritative" gone; note that a version reaches PyPI when its tag is pushed); clone + `setup.sh` demoted to Step 3 for unreleased code / development; Verify uses the `llmwiki` entry point.
- N7 `docs/UPGRADING.md`: "before v2.1.1" → "before the rename".
- N9 `release.yml`: no `sleep 30` after the fifth install attempt.
- Checks: `ruff check llmwiki tests scripts` clean; `tests/test_install_docs_match_packaging.py`, `tests/test_release_pipeline.py`, `tests/test_v03.py`, `tests/test_install_hint.py` green.

## commit-push
- Applied review keeps: N1–N7 + N9; N8 intentional
- Staging for commit on fix/210-pypi-install-docs; review.md gitignored
- Next remote: open PR, watch CI (stop writing this log after PR opens)
