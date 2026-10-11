# Tasks: Bound and speed up known-names preparation (#264)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** Completed

---

- [x] **Slice 1: Candidate cap + config defaults**

  > Operators with large vaults send at most `candidate_cap` topics (default 150), highest reach first; below-cut cache entries remain usable.
  - [x] Add `resolve_known_names_config(cfg, backend_page_timeout)` (or equivalent) reading `synthesis.known_names.candidate_cap` (default 150) and `synthesis.known_names.timeout` (default `max(600, backend_page_timeout)`); clamp invalid values with a warning. **[Agent: generalPurpose]**
  - [x] Cap `build_candidates` output (sort by `sessions` desc, `name` asc) and thread the capped list into `render_consolidation_prompt` / `prepare_known_names`. **[Agent: generalPurpose]**
  - [x] Tests: over-cap vault sends exactly the cap in highest-reach order; unset config uses 150 / `max(600, page)`. Extend `tests/test_topics.py` (or feature-slug file). Run focused pytest + ruff on touched files. **[Agent: generalPurpose]**
  - [x] Verify: focused pytest for cap/config green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Incremental reuse (fingerprint skip + delta merge)**

  > Steady-state vaults make zero known-names LLM calls; delta runs merge without losing untouched entries (including `kind`).
  - [x] Implement reach buckets + per-candidate `source_sig` + capped-set `inputs_fingerprint`; bump cache to `version: 2`; migrate v1 on next successful write. **[Agent: generalPurpose]**
  - [x] `prepare_known_names`: skip LLM when fingerprint/coverage matches; else prompt with delta only; merge via extended `parse_and_cache` (or successor) preserving untouched description/aliases/kind/distinct_from. **[Agent: generalPurpose]**
  - [x] Tests: second identical run → zero `synthesize_source_page` calls + kinds still loadable; one new candidate → one delta call + merge keeps prior topic fields; malformed reply does not corrupt on-disk cache. **[Agent: generalPurpose]**
  - [x] Verify: focused pytest for skip/merge green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 3: Dedicated timeout + run reporting**

  > Known-names uses its own timeout; run log shows counts, sizes, duration (and usage when available); skip path is visible.
  - [x] Add kw-only `timeout: float | None = None` to `BaseSynthesizer.synthesize_source_page` and Claude/Cursor/Ollama (+ Dummy accept/ignore); when set, use it instead of page timeout scaling. Wire `prepare_known_names` to pass resolved known-names timeout. **[Agent: generalPurpose]**
  - [x] Extend progress/warning output: mode (full/delta/skip), candidates considered/sent, prompt/reply bytes, duration; tokens/cost when backend reports them. **[Agent: generalPurpose]**
  - [x] Tests: spy asserts timeout kwarg; skip and success reporting lines (stdout capture, style of #181 tests). **[Agent: generalPurpose]**
  - [x] Verify: focused pytest for timeout/reporting green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 4: Docs + CHANGELOG (how to choose the cap)**

  > Operators can tune and understand the cap without reading the issue tracker.
  - [x] `docs/configuration-reference.md`: document `synthesis.known_names.*` and the FR5 how-to-choose guidance (bounds ≠ article size; cost/time; quality; exceeding ~150 ≈ large or noisy vault). Short pointer in `docs/reference/cli.md`; `CHANGELOG.md` `[Unreleased]`. **[Agent: generalPurpose]**
  - [x] Verify: spot-check docs contain default 150, timeout key, and the four guidance points; no ruff for md. **[Agent: generalPurpose]**

- [x] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: [spec-directory]` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]** *(fallback: generalPurpose after testing-expert usage limit)*
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]** *(fallback: generalPurpose)*
