# Tasks: Mirror synth unit tests under tests/synth/ (#318)

- [ ] **Slice 1: Layout gates name `tests/synth/`**
  - [ ] Extend `docs/CODING_STANDARDS.md` so the mirror rule names `tests/synth/` alongside `tests/cli/`, `tests/render/`, `tests/mcp/`, and `tests/adapters/`. Extend `tests/test_quality_gates.py` DOC assert + a layout gate that `tests/synth/` has `test_*.py` modules (existing package/`__init__.py` may remain — do not invent a hard-coded migrated-filename inventory). Annotate with `@spec: 417-synth-tests-consolidate`. No product code changes. **[Agent: generalPurpose]**
  - [ ] Verify: `python3 -m pytest tests/test_quality_gates.py -q` passes (DOC + layout once modules exist; after Slice 2 the layout gate is fully satisfied); `ruff check tests/test_quality_gates.py`. Delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 2: Migrate bounded synth batch**
  - [ ] Move/consolidate the approved batch into `tests/synth/` per technical-considerations §2.1 (backends_shared, claude_cli, cursor_cli, pipeline, raw_docs, dedup/stub/numeric, estimate, path, run_summary, parallel, parallel_acceptance; keep existing `test_reporting.py`). Fix `REPO_ROOT` via `tests._paths` where `parents[1]` would break. Drop `test_synth_` / `test_synthesize_` filename prefixes. Leave stay-put modules alone. No product behaviour change. **[Agent: generalPurpose]**
  - [ ] Apply #280-style hygiene inside the batch only: merge exact-duplicate parallel unit vs acceptance outcomes; delete vacuous/tautology asserts; one-sentence behaviour docstring per touched test or parametrize group. Keep usage accounting, interrupt/Ctrl+C drain, and backend mock contracts explicit. Do not delete to hit a count target. Grep and update any docs/tests that hardcode old flat paths for moved modules. **[Agent: generalPurpose]**
  - [ ] Verify: `ruff check llmwiki tests scripts`; `python3 -m pytest tests/synth/ -q`; `python3 -m pytest tests/ -q`; coverage `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` ≥87%. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 3: Contributor-visible notes**
  - [ ] Update `CHANGELOG.md` `[Unreleased]` by editing the existing testing/standards / mirror-layout bullets to add #318 / `tests/synth/` (prefer extend over a separate “synth tests moved” entry). Ensure `context/spec/417-synth-tests-consolidate/` flow-log reflects decisions. Privacy-clean. **[Agent: generalPurpose]**
  - [ ] Verify: CHANGELOG / standards / quality gates consistent; no personal paths. **[Agent: generalPurpose]**

- [ ] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Prefer extending `tests/test_quality_gates.py` invariants for `tests/synth/` layout (modules present + CODING_STANDARDS mention; optionally assert flat `tests/test_synth*.py` / `tests/test_synthesize*.py` originals from the batch are gone, without inventing a hard-coded inventory of *new* filenames) over inventing product synth behaviour tests. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 417-synth-tests-consolidate` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
