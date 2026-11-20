# Tasks: Mirror adapter unit tests under tests/adapters/ (#317)

- [ ] **Slice 1: Scaffold `tests/adapters/` + layout gates**
  - [ ] Create `tests/adapters/` (and `tests/adapters/contrib/` placeholder ready for Slice 2). No product code changes. Prefer `from tests._paths import REPO_ROOT` in moved modules that need repo root. Do **not** add ticket-only `__init__.py` (match #316 MCP convention). Annotate with `# @spec: 416-adapter-tests-consolidate` / `#317` on new modules when added. **[Agent: generalPurpose]**
  - [ ] Extend `docs/CODING_STANDARDS.md` so the mirror rule names `tests/adapters/` alongside `tests/cli/`, `tests/render/`, and `tests/mcp/`. Extend `tests/test_quality_gates.py` with invariant checks that `tests/adapters/` exists with `test_*.py` modules (and `contrib/` has `test_*.py` once Slice 2 lands) and that CODING_STANDARDS mentions `tests/adapters/`. Annotate with `@spec: 416-adapter-tests-consolidate`. Do not hard-code a migrated-filename inventory. **[Agent: generalPurpose]**
  - [ ] Verify: `python3 -m pytest tests/test_quality_gates.py -q` passes once a placeholder `test_*.py` exists or after Slice 2 lands in the same PR; `ruff check tests/adapters tests/test_quality_gates.py`. Delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 2: Migrate bounded adapter batch**
  - [ ] Move/consolidate the approved batch into `tests/adapters/` per technical-considerations §2.1 (registry, config, settings, is_available, headless contract + exclude_headless, tag, graduation, no_phantoms; contrib: chatgpt, copilot, cursor_ide, openclaw_cursor_cli, opencode). Fix any `Path(__file__)` depth issues. Drop flat `test_adapter_` / `*_adapter` filename prefixes as mapped. No product behaviour change. **[Agent: generalPurpose]**
  - [ ] Apply #280-style hygiene inside the batch only: merge exact-duplicate contract cases; delete vacuous/tautology asserts; one-sentence behaviour docstring per touched test or parametrize group. Keep per-adapter enable/sync and registry/availability/headless contracts explicit. Do not delete to hit a count target. Grep and update any docs/tests that hardcode old flat paths for moved modules. **[Agent: generalPurpose]**
  - [ ] Verify: `ruff check llmwiki tests scripts`; `python3 -m pytest tests/adapters/ -q`; `python3 -m pytest tests/ -q`; coverage `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` ≥87%. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 3: Contributor-visible notes**
  - [ ] Update `CHANGELOG.md` `[Unreleased]` by extending the existing testing/standards and mirror-layout bullets with #317 / `tests/adapters/` (prefer edit-in-place over a separate “adapters tests moved” entry). Ensure `context/spec/416-adapter-tests-consolidate/` flow-log reflects decisions. Privacy-clean. **[Agent: generalPurpose]**
  - [ ] Verify: CHANGELOG / standards / quality gates consistent; no personal paths. **[Agent: generalPurpose]**

- [ ] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Prefer extending `tests/test_quality_gates.py` invariants for `tests/adapters/` layout (dir + modules + CODING_STANDARDS mention; optionally assert flat batch originals are gone) over inventing product adapter protocol tests. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 416-adapter-tests-consolidate` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
