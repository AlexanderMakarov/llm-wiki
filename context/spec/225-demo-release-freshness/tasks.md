# Tasks: Pages-only demo session freshness (#225)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Worktree: `.claude/worktrees/feat-225-demo-session-freshness-gate`. Drive `python3 -m llmwiki` from the worktree. Mutating vault commands use `$TMP_VAULT` (`.worktree-vault`) only — never the live Obsidian vault. Do **not** commit regenerated `demo/` from CI experiments; Option A is Pages-only.

Hired specialists: **generalPurpose** for implementation; **testing-expert** for test / Feature Testing slices. (No dedicated github-ci agent — use generalPurpose for workflow YAML.)

---

- [x] **Slice 1: Scheduled Pages workflow (sessions redate → build → deploy)**

  > End state: `.github/workflows/demo-session-freshness.yml` exists with cron `0 4 */6 * *` + `workflow_dispatch`; checks out `main`; runs offline `generate_demo_sessions.py --today` (UTC); reconcile + build + Pages deploy; version assert; shared `pages` concurrency; **no** synth, **no** git push, **no** `refresh_demo.py`.

  - [x] Add `.github/workflows/demo-session-freshness.yml` per technical-considerations.md (permissions, concurrency group `pages` / `cancel-in-progress: false`, environment `github-pages`, Python 3.12 + markdown, generate_demo_sessions with `date -u +%F`, reconcile_synth_state_from_wiki, build `--vault demo --out ./site --local-root /home/user`, `.nojekyll`, upload + deploy-pages, `check_live_version.py`). Hard-exclude synth / git write / refresh_demo. **[Agent: generalPurpose]**
  - [x] Add workflow contract tests in `tests/test_demo_session_freshness_workflow.py` (feature slug, not issue-number filename): cron string, workflow_dispatch, generate_demo_sessions + build + deploy present; no `git push` / `llmwiki synth` / `refresh_demo`; concurrency group `pages`; checkout is default/`main` (not release-tag-only). Annotate `@spec: 225-demo-release-freshness`. **[Agent: testing-expert]**
  - [x] Verify: `ruff check tests/test_demo_session_freshness_workflow.py`; `python3 -m pytest tests/test_demo_session_freshness_workflow.py -q`. Delete any ephemeral artifacts. **[Agent: testing-expert]**

- [x] **Slice 2: Generator confidence for the CI write path**

  > End state: tests prove `generate_demo_sessions.py --today` stays offline, rehomes source pages, and fails closed on migrate errors — so the schedule on `main` cannot silently call a broken generator.

  - [x] Review `tests/test_generate_demo_sessions.py`; extend only where gaps remain for the CI write path (offline/no LLM, rehome on real write, non-zero when migrate reports errors). Do not regenerate committed `demo/` as part of the default happy path — use tmp vaults / mocks. **[Agent: testing-expert]**
  - [x] If the module docstring still says CI/pages never regenerate the corpus, update it to: schedule may redate on the runner for Pages-only; still never commits. **[Agent: generalPurpose]**
  - [x] Verify: `ruff check scripts/generate_demo_sessions.py tests/test_generate_demo_sessions.py`; `python3 -m pytest tests/test_generate_demo_sessions.py -q`. **[Agent: testing-expert]**

- [x] **Slice 3: Docs + release skill describe the two publishers**

  > End state: RELEASE_PROCESS, uptime, github-pages, REFRESH_DEMO, and `/release` skill no longer claim “no scheduled freshness”; they document release (committed full refresh) vs schedule (Pages-only session slide from `main`, no git write, no synth, version = main `__version__`). CHANGELOG Unreleased bullet for #225.

  - [x] Update `docs/maintainers/RELEASE_PROCESS.md`, `docs/uptime.md`, `docs/deploy/github-pages.md`, `docs/maintainers/REFRESH_DEMO.md`, and `.claude/skills/release/SKILL.md` per FR2/FR4/FR5/FR6/FR7. **[Agent: generalPurpose]**
  - [x] Add/adjust CHANGELOG `[Unreleased]` entry for the Pages-only every-`*/6` session freshness job (#225). **[Agent: generalPurpose]**
  - [x] Extend release-skill / pages docs contract tests (e.g. `tests/test_209_release_skill.py` and/or `tests/test_pages_deploy.py`) so they assert the new schedule is documented and the old “no scheduled freshness workflow” claim is gone. **[Agent: testing-expert]**
  - [x] Verify: `python3 -m pytest tests/test_209_release_skill.py tests/test_pages_deploy.py tests/test_demo_session_freshness_workflow.py -q`; spot-check docs for the banned stale phrases. **[Agent: testing-expert]**

- [x] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.

  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 225-demo-release-freshness` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
