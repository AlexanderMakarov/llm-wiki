# Tasks: Mirror static-site / render unit tests under tests/render/ (#315)

- [ ] **Slice 1: Scaffold `tests/render/` + layout gates**
  - [ ] Create `tests/render/__init__.py` (package docstring + `# @spec: 414-tests-render-mirror` / `#315`) and `tests/render/_paths.py` (`REPO_ROOT = Path(__file__).resolve().parents[2]`, CLI pattern). No product code changes. **[Agent: generalPurpose]**
  - [ ] Extend `docs/CODING_STANDARDS.md` so the mirror rule names `tests/render/` alongside `tests/cli/`. Extend `tests/test_quality_gates.py` with invariant checks that `tests/render/` exists as a package with `test_*.py` modules and that CODING_STANDARDS mentions `tests/render/`. Annotate with `@spec: 414-tests-render-mirror`. **[Agent: generalPurpose]**
  - [ ] Verify: `python3 -m pytest tests/test_quality_gates.py -q` passes once a placeholder `test_*.py` exists or after Slice 2 lands in the same PR; `ruff check tests/render tests/test_quality_gates.py`. Delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 2: Migrate bounded render/static-site batch**
  - [ ] Move/consolidate the approved batch into `tests/render/` per technical-considerations §2.1 (split, is_subagent, chrome, palette_a11y, palette_indexes, palette_match from `test_248_*`, documents_tree_filter, raw_docs_site, wcag_contrast, static_site, candidates_site, session_toc, sessions_index + filter_slug_label merge if same surface, collapse_section, chip_contrast merge into wcag if duplicate). Fix `REPO_ROOT` via `_paths`; add optional `_js_harness.py` only if ≥2 modules share node extract/run. Drop issue-digit filenames. No product behaviour change. **[Agent: generalPurpose]**
  - [ ] Apply #280-style hygiene inside the batch only: merge duplicates, delete vacuous/tautology asserts, one-sentence behaviour docstring per touched test or parametrize group. Do not delete to hit a count target. Grep and update any docs/tests that hardcode old flat paths for moved modules. **[Agent: generalPurpose]**
  - [ ] Verify: `ruff check llmwiki tests scripts`; `python3 -m pytest tests/render/ -q`; `python3 -m pytest tests/ -q`; coverage `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` ≥87%. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 3: Contributor-visible notes**
  - [ ] Update `CHANGELOG.md` `[Unreleased]` only if the standards/layout mention is user-or-contributor-visible as a distinct note; prefer editing an existing Unreleased testing/standards bullet if one already covers mirror layout. Ensure `context/spec/414-tests-render-mirror/` flow-log reflects decisions. Privacy-clean. **[Agent: generalPurpose]**
  - [ ] Verify: CHANGELOG / standards / quality gates consistent; no personal paths. **[Agent: generalPurpose]**

- [ ] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Prefer extending `tests/test_quality_gates.py` invariants for `tests/render/` layout over inventing product HTML tests. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 414-tests-render-mirror` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
