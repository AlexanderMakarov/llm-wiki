# Tasks: Mirror MCP unit tests under tests/mcp/ (#316)

- [x] **Slice 1: Scaffold `tests/mcp/` + layout gates**
  - [x] Create `tests/mcp/__init__.py` (package docstring + `# @spec: 415-mcp-tests-consolidate` / `#316`). No product code changes. Prefer `from tests._paths import REPO_ROOT` in moved modules that need repo root (do not add nested `_paths.py` unless required). **[Agent: generalPurpose]**
  - [x] Extend `docs/CODING_STANDARDS.md` so the mirror rule names `tests/mcp/` alongside `tests/cli/` and `tests/render/`. Extend `tests/test_quality_gates.py` with invariant checks that `tests/mcp/` exists as a package with `test_*.py` modules and that CODING_STANDARDS mentions `tests/mcp/`. Annotate with `@spec: 415-mcp-tests-consolidate`. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/test_quality_gates.py -q` passes once a placeholder `test_*.py` exists or after Slice 2 lands in the same PR; `ruff check tests/mcp tests/test_quality_gates.py`. Delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Migrate bounded MCP batch**
  - [x] Move/consolidate the approved batch into `tests/mcp/` per technical-considerations §2.1 (protocol, tools from enhanced, safety, byte_cap, read_page_allowlist, lint_parity, caller_attribution, usage, wiki_add with timeout/lock kept explicit, add_cli_proxy with proxy acceptance kept explicit). Fix protocol `REPO_ROOT` via `tests._paths`. Drop `test_mcp_` filename prefixes. No product behaviour change. **[Agent: generalPurpose]**
  - [x] Apply #280-style hygiene inside the batch only: merge exact-duplicate default-build / synth-opt-in slices between wiki_add and add_cli_proxy when both assert the same outcome; delete vacuous/tautology asserts; one-sentence behaviour docstring per touched test or parametrize group. Keep timeout/poll, lock-holder, and CLI-proxy acceptance contracts explicit. Do not delete to hit a count target. Grep and update any docs/tests that hardcode old flat paths for moved modules (`test_102_acceptance.py`, `test_150_acceptance.py`, etc.). **[Agent: generalPurpose]**
  - [x] Verify: `ruff check llmwiki tests scripts`; `python3 -m pytest tests/mcp/ -q`; `python3 -m pytest tests/ -q`; coverage `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` ≥87%. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 3: Contributor-visible notes**
  - [x] Update `CHANGELOG.md` `[Unreleased]` only if the standards/layout mention is user-or-contributor-visible as a distinct note; prefer editing an existing Unreleased testing/standards bullet if one already covers mirror layout. Ensure `context/spec/415-mcp-tests-consolidate/` flow-log reflects decisions. Privacy-clean. **[Agent: generalPurpose]**
  - [x] Verify: CHANGELOG / standards / quality gates consistent; no personal paths. **[Agent: generalPurpose]**

- [x] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Prefer extending `tests/test_quality_gates.py` invariants for `tests/mcp/` layout (package + modules + CODING_STANDARDS mention; optionally assert flat `tests/test_mcp_*.py` originals are gone) over inventing product MCP protocol tests. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 415-mcp-tests-consolidate` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
