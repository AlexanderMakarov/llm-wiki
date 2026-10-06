# Tasks: Quality gates for useful, fast tests (#280)

- [x] **Slice 1: Unit coverage gate at 87%**
  - [x] Add `pytest-cov` to `[project.optional-dependencies] dev` only; add `[tool.coverage.run] source = ["llmwiki"]` and `[tool.coverage.report] fail_under = 87` in `pyproject.toml`. Do not put `--cov` in default `addopts`. **[Agent: general-purpose]**
  - [x] Update `.github/workflows/ci.yml` `lint-and-test` to install `pytest-cov` and run `python -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (no extra `-q`). Keep e2e ignored via existing `addopts`. **[Agent: general-purpose]**
  - [x] Verify: from worktree, install `.[dev]` in a venv if needed; run the CI-equivalent pytest cov command; confirm exit 0 with coverage ≥87%; `ruff check` on any touched Python. **[Agent: general-purpose]**
    - Note: unblocked by fixing false-positive `build/` package detection, adding `build` to dev/CI, and excluding `@pytest.mark.slow` from default `addopts` so wall-clock lint_perf does not flake under cov (coverage stayed 87.33%).

- [x] **Slice 2: CODING_STANDARDS + CONTRIBUTING + agent pointers**
  - [x] Add `docs/CODING_STANDARDS.md` per technical-considerations (usefulness, unit cov ≥87%, mirror layout, no one-module-per-feature / `test_<digits>_*.py`, behavior docstrings, PIT weak-test patterns, no wall-clock outside slow perf, isolation, behavior-preserving cleanups, TDD encouraged, mutation as gap measurement). **[Agent: general-purpose]**
  - [x] Update `CONTRIBUTING.md` §Testing: parked-branch “before adding a test” content (adapt); exact cov/e2e command blocks; 87% floor in `pyproject.toml`; pointer to `docs/CODING_STANDARDS.md`; layout/consolidation + skip policy. Update short pointers in `.claude/rules/contributing.md`, `.cursor/rules/contributing.mdc`, `.kiro/steering/contributing-rules.md` without conflicting long copies. **[Agent: general-purpose]**
  - [x] Update `.claude/agents/testing-expert.md` with #280 guardrail rules (extend mirrored modules; fewest checks; behavior docstring; no wall-clock default; cov floor finding; dead-skip delete). Point `.cursor/agents/testing-expert.md` (and `.kiro` if applicable) via **symlink** to the `.claude` file, or a short stub link if symlink unsupported — no duplicated body. **[Agent: general-purpose]**
  - [x] Verify: docs paths resolve; no personal vault paths; symlink/stub loads from Cursor allowlist; `ruff`/pytest still green for unrelated suites if touched. **[Agent: general-purpose]**

- [x] **Slice 3: Agnix local + CI (kit + inner tooling) with triage gate**
  - [x] Document local agnix commands for `llmwiki/agent_kit` and scoped inner paths (`.claude/skills`, `.claude/agents`, relevant commands). Pin tool version. **[Agent: general-purpose]**
  - [x] Add CI job/step(s) running agnix on kit + agreed inner paths (not full-repo demo scan). **[Agent: general-purpose]**
  - [x] **Stop for maintainer:** run agnix locally first; present important findings; ask fix-in-this-PR vs postpone as GitHub issues. Apply only the chosen fixes before treating CI as green. **[Agent: general-purpose]**
  - [x] Verify: documented commands run; CI workflow YAML valid; chosen findings fixed or issues filed. **[Agent: general-purpose]**

- [x] **Slice 4: CLI batch — dead skips + mirrored consolidation (guardrail proof)**
  - [x] Delete permanently skipped “subcommand removed” tests repo-wide (prefer all ~27). **[Agent: general-purpose]**
  - [x] Consolidate CLI-focused unit tests into mirrored `tests/cli/` (and helpers as needed): merge cases into package modules rather than renaming to new one-feature files; keep issue/spec refs in docstrings/`# @spec:`; add one-sentence behavior docstrings on touched tests. No product behavior change. **[Agent: general-purpose]**
  - [x] Apply CODING_STANDARDS / testing-expert rules to that batch (weak asserts, wall-clock outside slow, empty-input greens). **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/cli/ tests/ --cov=llmwiki --cov-report=term-missing` (or equivalent) stays ≥87%; no `subcommand removed` skip markers left; `ruff check` on touched paths. **[Agent: general-purpose]**

- [x] **Slice 5: CLI mutation experiment (gap report, not test dump)**
  - [x] Run scoped mutation (e.g. mutmut) on CLI product surface (`llmwiki/cli.py` + minimal helpers owned by the batch). Time-box; record partial results if needed. **[Agent: general-purpose]**
  - [x] Write `context/spec/280-shrink-test-suite/mutation-experiment.md`: survivor counts/examples; which classes guardrails already cover vs miss; any **modest** guardrail tweaks made. Do **not** bulk-write unit tests from survivors. **[Agent: general-purpose]**
  - [x] **Stop for maintainer:** present the gap report and ask whether to file mutation testing as an **important** follow-up issue or skip it. **[Agent: general-purpose]**
  - [x] Verify: experiment notes committed; unit cov gate still green after any guardrail-only tweaks. **[Agent: general-purpose]**
    - Note: notes are on disk (`mutation-experiment.md`); commit is Step 9 of implement-feature. Coverage after guardrail tweaks was 87.33%. Maintainer chose: file mutation as **important** follow-up (not every-PR CI).

- [x] **Slice 6: Follow-up issues + CHANGELOG**
  - [x] File separate GitHub issues for non-CLI test-layout migrations (site/render, MCP, adapters, synth, …) with bounded scope. **[Agent: general-purpose]**
  - [x] `CHANGELOG.md` Unreleased entry for coverage CI 87%, CODING_STANDARDS, testing-expert/agnix, CLI consolidation, mutation experiment pointer. **[Agent: general-purpose]**
  - [x] Verify: issue URLs listed in flow-log or mutation notes; CHANGELOG under Unreleased; privacy clean. **[Agent: general-purpose]**

- [x] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Add **minimal** acceptance checks for the gates themselves (e.g. `fail_under` present, dead-skip markers gone, CODING_STANDARDS names the floor and `tests/cli/` layout, CLI tests live under `tests/cli/`) in `tests/test_quality_gates.py`. Annotate with `@spec: 280-shrink-test-suite`. Prefer verifying configuration and invariants over inventing product tests. **[Agent: testing-expert]**
  - [x] Run those checks plus the unit suite with coverage. All must pass (≥87%). Fix any failures before proceeding. **[Agent: testing-expert]**
