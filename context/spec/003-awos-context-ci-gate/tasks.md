# Tasks: Spec-first AWOS context CI gate (#117)

- **Spec:** `003-awos-context-ci-gate`
- **Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/117
- **Notes:** No dedicated `github-ci-packaging` agent — implementation uses `generalPurpose`. Feature Testing & Regression uses `testing-expert`.

---

- [x] **Slice 1: Path gate module + unit tests**
  - [x] Implement `tests/awos_context_gate.py` with armed prefixes, `context/` satisfaction, pure path-list predicates, and CLI (`--base`/`--head` via `git diff --name-only` + merge-base already supplied by caller, or compute merge-base when given raw SHAs — match tech spec). Quiet exit 0 on pass; `::error::` + exit 1 on fail. **[Agent: generalPurpose]**
  - [x] Add `tests/test_awos_context_gate.py` covering exempt-only pass, armed+context pass, armed-without-context fail, and tutorial/scripts exempt edges. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/test_awos_context_gate.py -q` passes; dry-run CLI on synthetic git if practical. Delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Wire `awos-context` job in pr-lint.yml**
  - [x] Add hard-fail job + header gate #4 comment; `checkout@v7` fetch-depth 0; merge-base then `python3 tests/awos_context_gate.py …`. No labeled triggers; no CHANGELOG job changes. **[Agent: generalPurpose]**
  - [x] Verify: YAML invokes the module; `rg` shows no `awos-exempt` / labeled trigger; header lists four gates. **[Agent: generalPurpose]**

- [x] **Slice 3: Contributor docs + changelog**
  - [x] Update `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/maintainers/REVIEW_CHECKLIST.md` (`## Meta`), and `CHANGELOG.md` Unreleased; keep PR checklist box-count test green. **[Agent: generalPurpose]**
  - [x] Verify: armed-path set and “no label bypass” appear consistently; `python3 -m pytest tests/test_pr_template.py -q` passes. **[Agent: generalPurpose]**

- [x] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 003-awos-context-ci-gate` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
