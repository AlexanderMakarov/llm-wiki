# Tasks: Honest Home pipeline stamps (#234)

- **Spec:** `234-home-timeline-automation-stamps`
- **Status:** Ready for implementation
- **Worktree:** `.claude/worktrees/feat-234-home-timeline-automation-stamps`
- **Vault:** `$WT/.worktree-vault` only for mutating `llmwiki` commands

---

- [ ] **Slice 1: Shared ops stamps + lint record helper (DRY)**

  - [ ] Extend `state_store.default_state` / `_ensure_shape` with `ops.last_synth_at`, `ops.last_build_at`, `ops.last_lint_status`, `ops.last_lint_error`. Add shared helpers: synth stamp, lint record (time + status + console-shaped error text + clear on ok), and extract/reuse `build_site`’s vault→`site/` `llmwiki-state.js` copy so lint can call the same function. Wire helpers from `cmd_synthesize` (non-estimate), `pipeline` synth stage, `build_site` (rc==0), `cmd_lint`, and `_run_lint_step` — no duplicated `__setitem__` blocks. **[Agent: general-purpose]**
  - [ ] Unit tests: shape defaults; synth/build/lint stamp writers; lint failed clears vs sets error (multiline); site data sidecar updates without HTML change; backend-unavailable synth does not stamp. **[Agent: general-purpose]**
  - [ ] Verify: targeted pytest green; `ruff check` on touched Python; delete ephemeral artifacts. **[Agent: general-purpose]**

- [ ] **Slice 2: Pipeline state UI — stage stamps + required lint banner**

  - [ ] Update `renderStateWidget`: show Last sync / Last synth / Last build / Last lint in **Pipeline state**; required banner above Pipeline state when `last_lint_error` non-empty (pre-wrap, ~6 lines); remove those four stamps as Timeline primary; hide dead Last reflect; CSS as needed. **[Agent: general-purpose]**
  - [ ] Update/extend `tests/test_state_widget.py` (and related) for stamps, banner empty vs present, Timeline non-duplication. **[Agent: general-purpose]**
  - [ ] Verify: widget tests green; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 3: Automation panel settings-only + shrink**

  - [ ] Shrink `render_automation_panel`: drop lint-fail reminder + Updated; merge hooks+watch and cost+backend; Maintain one-liner (site once after synth); no stage stamps. Touch docs (`cli` / `ui` / `state-persistence` / UPGRADING / CHANGELOG) + `context/` as CONTRIBUTING requires. **[Agent: general-purpose]**
  - [ ] Update Automation panel HTML assertions (`test_automation_install` etc.). **[Agent: general-purpose]**
  - [ ] Verify: automation + docs-related tests green; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 4: Pipeline continue / lint-fail keeps build — acceptance behavior**

  - [ ] Confirm/tests: without `--fail-fast`, synth failure still runs build; with `--fail-fast`, later stages skip (console reports). `all --lint-fail errors` with planted findings: exit 2, site HTML from this build remains, state has failed + error, site data sidecar reflects banner fields. **[Agent: general-purpose]**
  - [ ] Verify: new/updated pipeline acceptance tests green against `$TMP_VAULT`; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 234-home-timeline-automation-stamps` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
