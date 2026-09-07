# Tasks: Cursor Agent CLI synthesis backend (#230)

- **Spec:** `226-cursor-cli-synth-backend`
- **Status:** Ready for implementation

---

- [ ] **Slice 1: Nested config loaders + `cursor_cli` backend resolves**

  - [ ] Add nested `synthesis.claude` reader (flat `claude_*` fallback) and `synthesis.cursor_cli` reader with default model `composer-2.5` (alias `composer` if CLI accepts). Wire `resolve_backend("cursor_cli")` to a `CursorCLISynthesizer` stub that builds lean argv (`-p`, `--mode ask`, `--sandbox enabled`, `--model`) and resolves `agent`/`cursor-agent` from PATH only. **[Agent: general-purpose]**
  - [ ] Unit tests: nested vs flat Claude load; cursor defaults; resolve_backend name; argv flags; unknown config backend still warns→dummy. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_synth_claude_cli.py tests/test_ollama_backend.py -q` plus new cursor config/argv tests pass; delete any ephemeral artifacts. **[Agent: general-purpose]**

- [ ] **Slice 2: Real Cursor subprocess synth + `--check` probe**

  - [ ] Implement `synthesize_source_page` (stdin or argv+body cap), thread-safe usage if any, `is_available` tiny live probe with timeout; hard-fail when unavailable (no failover). **[Agent: general-purpose]**
  - [ ] Mocked subprocess unit tests for success, timeout, missing binary, probe failure. **[Agent: general-purpose]**
  - [ ] Verify: new cursor_cli tests green with mocks only; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 3: `synth --backend` override (check / estimate / run)**

  - [ ] Add `--backend` to synth argparse; overlay `synthesis.backend` for the process; reject unknown names (exit 2); honor on `--check` and `--estimate`; estimate reads nested cursor/claude model. Do not write config.json. **[Agent: general-purpose]**
  - [ ] CLI tests for override, unknown rejection, estimate model selection. **[Agent: general-purpose]**
  - [ ] Verify: targeted pytest for CLI synth backend flags green; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 4: Overview follows active backend (dummy spends nothing)**

  - [ ] Refactor `build.py` overview path to use resolved synthesis backend; skip LLM when dummy/unavailable; support cursor_cli and claude (and ollama if already plausible) with mocks. **[Agent: general-purpose]**
  - [ ] Update overview safety tests; add dummy-skips-LLM and cursor path tests. **[Agent: general-purpose]**
  - [ ] Verify: overview-related tests green; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 5: `model_pricing.csv` Cursor rows + docs / automation UX**

  - [ ] Add Composer/Grok (and practical Agent CLI aliases) from Cursor published pricing; label any Kimi K3 stand-in; update configuration / CLI / synthesis-cost / UPGRADING / CHANGELOG; install-automation backend list; distinguish synth backend vs ingest adapter; touch `context/` as required. **[Agent: general-purpose]**
  - [ ] Pricing resolution tests for new aliases; docs link sanity as needed. **[Agent: general-purpose]**
  - [ ] Verify: pricing + estimate tests green; `ruff check` on touched Python; cleanup. **[Agent: general-purpose]**

- [ ] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 226-cursor-cli-synth-backend` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
