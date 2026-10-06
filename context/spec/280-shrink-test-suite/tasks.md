# Tasks: Quality gates for useful, fast tests (#280)

- [ ] **Slice 1: Unit coverage gate at 87%**
  - [ ] Add `pytest-cov` to `[project.optional-dependencies] dev` only; add `[tool.coverage.run] source = ["llmwiki"]` and `[tool.coverage.report] fail_under = 87` in `pyproject.toml`. Do not put `--cov` in default `addopts`. **[Agent: general-purpose]**
  - [ ] Update `.github/workflows/ci.yml` `lint-and-test` to install `pytest-cov` and run `python -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (no extra `-q`). Keep e2e ignored via existing `addopts`. **[Agent: general-purpose]**
  - [ ] Verify: from worktree, install `.[dev]` in a venv if needed; run the CI-equivalent pytest cov command; confirm exit 0 with coverage ≥87%; `ruff check` on any touched Python. **[Agent: general-purpose]**

- [ ] **Slice 2: CODING_STANDARDS + CONTRIBUTING + agent pointers**
  - [ ] Add `docs/CODING_STANDARDS.md` per technical-considerations (usefulness, unit cov ≥87%, mirror layout, no one-module-per-feature / `test_<digits>_*.py`, behavior docstrings, PIT weak-test patterns, no wall-clock outside slow perf, isolation, behavior-preserving cleanups, TDD encouraged, mutation as gap measurement). **[Agent: general-purpose]**
  - [ ] Update `CONTRIBUTING.md` §Testing: parked-branch “before adding a test” content (adapt); exact cov/e2e command blocks; 87% floor in `pyproject.toml`; pointer to `docs/CODING_STANDARDS.md`; layout/consolidation + skip policy. Update short pointers in `.claude/rules/contributing.md`, `.cursor/rules/contributing.mdc`, `.kiro/steering/contributing-rules.md` without conflicting long copies. **[Agent: general-purpose]**
  - [ ] Update `.claude/agents/testing-expert.md` with #280 guardrail rules (extend mirrored modules; fewest checks; behavior docstring; no wall-clock default; cov floor finding; dead-skip delete). Point `.cursor/agents/testing-expert.md` (and `.kiro` if applicable) via **symlink** to the `.claude` file, or a short stub link if symlink unsupported — no duplicated body. **[Agent: general-purpose]**
  - [ ] Verify: docs paths resolve; no personal vault paths; symlink/stub loads from Cursor allowlist; `ruff`/pytest still green for unrelated suites if touched. **[Agent: general-purpose]**

- [ ] **Slice 3: Agnix local + CI (kit + inner tooling) with triage gate**
  - [ ] Document local agnix commands for `llmwiki/agent_kit` and scoped inner paths (`.claude/skills`, `.claude/agents`, relevant commands). Pin tool version. **[Agent: general-purpose]**
  - [ ] Add CI job/step(s) running agnix on kit + agreed inner paths (not full-repo demo scan). **[Agent: general-purpose]**
  - [ ] **Stop for maintainer:** run agnix locally first; present important findings; ask fix-in-this-PR vs postpone as GitHub issues. Apply only the chosen fixes before treating CI as green. **[Agent: general-purpose]**
  - [ ] Verify: documented commands run; CI workflow YAML valid; chosen findings fixed or issues filed. **[Agent: general-purpose]**

- [ ] **Slice 4: CLI batch — dead skips + mirrored consolidation (guardrail proof)**
  - [ ] Delete permanently skipped “subcommand removed” tests repo-wide (prefer all ~27). **[Agent: general-purpose]**
  - [ ] Consolidate CLI-focused unit tests into mirrored `tests/cli/` (and helpers as needed): merge cases into package modules rather than renaming to new one-feature files; keep issue/spec refs in docstrings/`# @spec:`; add one-sentence behavior docstrings on touched tests. No product behavior change. **[Agent: general-purpose]**
  - [ ] Apply CODING_STANDARDS / testing-expert rules to that batch (weak asserts, wall-clock outside slow, empty-input greens). **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/cli/ tests/ --cov=llmwiki --cov-report=term-missing` (or equivalent) stays ≥87%; no `subcommand removed` skip markers left; `ruff check` on touched paths. **[Agent: general-purpose]**

- [ ] **Slice 5: CLI mutation experiment (gap report, not test dump)**
  - [ ] Run scoped mutation (e.g. mutmut) on CLI product surface (`llmwiki/cli.py` + minimal helpers owned by the batch). Time-box; record partial results if needed. **[Agent: general-purpose]**
  - [ ] Write `context/spec/280-shrink-test-suite/mutation-experiment.md`: survivor counts/examples; which classes guardrails already cover vs miss; any **modest** guardrail tweaks made. Do **not** bulk-write unit tests from survivors. **[Agent: general-purpose]**
  - [ ] **Stop for maintainer:** present the gap report and ask whether to file mutation testing as an **important** follow-up issue or skip it. **[Agent: general-purpose]**
  - [ ] Verify: experiment notes committed; unit cov gate still green after any guardrail-only tweaks. **[Agent: general-purpose]**

- [ ] **Slice 6: Follow-up issues + CHANGELOG**
  - [ ] File separate GitHub issues for non-CLI test-layout migrations (site/render, MCP, adapters, synth, …) with bounded scope. **[Agent: general-purpose]**
  - [ ] `CHANGELOG.md` Unreleased entry for coverage CI 87%, CODING_STANDARDS, testing-expert/agnix, CLI consolidation, mutation experiment pointer. **[Agent: general-purpose]**
  - [ ] Verify: issue URLs listed in flow-log or mutation notes; CHANGELOG under Unreleased; privacy clean. **[Agent: general-purpose]**

- [ ] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Add **minimal** acceptance checks for the gates themselves (e.g. `fail_under` present, dead-skip markers gone, CODING_STANDARDS exists, CLI tests live under `tests/cli/`) — consolidate into an existing meta/helpers test module or a small mirrored place; do **not** add `test_280_acceptance.py`. Annotate with `@spec: 280-shrink-test-suite`. Prefer verifying configuration and invariants over inventing product tests. **[Agent: testing-expert]**
  - [ ] Run those checks plus the unit suite with coverage. All must pass (≥87%). Fix any failures before proceeding. **[Agent: testing-expert]**
