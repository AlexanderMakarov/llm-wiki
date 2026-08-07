# Tasks: Honest already-synthesized counts

- **Spec:** `006-honest-synthesized-counts`
- **Issue:** #81

---

- [ ] **Slice 1: Estimate report keys + honest CLI Corpus / Already synthesized / Source pages**

  > `synth --estimate` prints eligible-source units and a current-state page/stub line.
  - [ ] Extend `synthesize_estimate_report` to expose `source_pages_on_disk` and `source_page_stubs` via `_scan_source_page_keys` (no second walk when avoidable). Keep existing corpus/synthesized input semantics. **[Agent: generalPurpose]**
  - [ ] Add `print_source_pages_current_state` (or equivalent) in `llmwiki/synth/reporting.py`. Update `_synthesize_estimate` stdout: Corpus eligible `(S sessions + D docs)`; Already synthesized `N of M eligible sources`; Source pages current-state line. Persist page/stub keys on `synth.estimate`. Drop `pages in wiki/sources/`. **[Agent: generalPurpose]**
  - [ ] Extend `tests/test_synthesize_estimate.py` for the new strings and forbid the old phrase. **[Agent: generalPurpose]**
  - [ ] Verify: run the updated estimate tests; remove ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 2: Home Pipeline honesty + page note on snapshot refresh**

  > Home caption/units match estimate; current-state page note appears when keys exist.
  - [ ] In `refresh_synth_pending` and build pipeline backfill, recompute and write `source_pages_on_disk` / `source_page_stubs` onto `synth.estimate`. **[Agent: generalPurpose]**
  - [ ] Update `llmwiki/render/js.py` files-layer caption to eligible sources; render muted Source pages current-state note under that table when estimate keys present; omit when absent. **[Agent: generalPurpose]**
  - [ ] Extend `tests/test_state_widget.py` for caption + note presence/absence. **[Agent: generalPurpose]**
  - [ ] Verify: run state-widget + related estimate tests; remove ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 3: Docs, CHANGELOG, roadmap**

  > Docs and product notes match the new labels.
  - [ ] Update `docs/reference/ui.md` (and any other docs that claim Files-layer page units). Add `CHANGELOG.md` Unreleased bullet for #81. Check off #81 in `context/product/roadmap.md`. Add any other required `context/` note for the AWOS context CI gate. **[Agent: generalPurpose]**
  - [ ] Verify: grep for remaining `pages in wiki/sources/` and misleading Files-layer unit claims; fix stragglers. **[Agent: generalPurpose]**

- [ ] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 006-honest-synthesized-counts` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
