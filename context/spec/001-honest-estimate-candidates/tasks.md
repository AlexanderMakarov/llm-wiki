# Tasks: Honest estimate Candidates + end-of-synth summary

- **Spec:** `001-honest-estimate-candidates`
- **Issue:** #113

---

- [x] **Slice 1: Estimate Candidates labelled as pre-run state**

  > Estimate output never reads as a forecast of the upcoming harvest.
  - [x] Add shared formatting helper for the pre-run Candidates block (label `Candidates (pre-run state):` + pending-sources note). Wire `_synthesize_estimate` to use it; update `summarize_backlog` docstring / CLI comments so they no longer call Candidates a “preview” of the next run. **[Agent: general-purpose]**
  - [x] Extend `tests/test_synthesize_estimate.py` (or adjacent) so estimate stdout includes the pre-run label and note; confirm estimate does not print the post-run summary. **[Agent: general-purpose]**
  - [x] Verify: run the new/updated estimate tests; clean any ephemeral artifacts. **[Agent: general-purpose]**

- [x] **Slice 2: End-of-run summary after real synth (and all --with-synth)**

  > Successful real synthesize ends with count, duration, and optional tokens/cost; Candidates stay on the harvest line only (no duplicate in the end summary).
  - [x] Implement `print_synth_run_summary` using wall clock + synthesize counts (+ tokens/cost when known). Call from `cmd_synthesize` and `llmwiki all --with-synth`. Do not reprint Candidates in the end summary. **[Agent: general-purpose]**
  - [x] Add CLI/integration tests (tmp vault) covering: post-run summary lines; single Candidates (harvest); no fabricated token/cost; `--sources-only` / estimate path behaviour. **[Agent: general-purpose]**
  - [x] Verify: run the new tests + a quick `pytest` subset for synth estimate; clean ephemeral artifacts. **[Agent: general-purpose]**

- [x] **Slice 3: Docs, Home copy, CHANGELOG**

  > User-facing docs no longer call estimate Candidates a preview.
  - [x] Update `docs/reference/cli.md`, `docs/cheatsheet.md`, `docs/reference/ui.md`, `docs/UPGRADING.md`, and `llmwiki/render/js.py` Home copy; add `CHANGELOG.md` Unreleased bullet for #113. **[Agent: general-purpose]**
  - [x] Verify: grep docs/js for remaining “preview” claims about estimate Candidates; fix stragglers; no ephemeral artifacts. **[Agent: general-purpose]**

- [x] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 001-honest-estimate-candidates` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
