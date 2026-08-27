# Tasks: Extend exclude_headless across agentic adapters (#180)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** Completed

---

- [x] **Slice 1: Adapter headless contract + convert choke point (Claude unchanged)**
  - [x] Add `BaseAdapter.is_headless_session(self, records) -> bool` and a registry/contract test that every registered adapter defines it. Move or wrap today’s Claude `entrypoint` / `promptSource` rule so `claude_code` (or the shared default used only by Claude) preserves current behavior. Wire `convert_all` to call the **adapter** method after `normalize_records`; keep aggregate headless sync summary (no per-adapter breakdown); persist `is_headless` on rendered raw markdown. **[Agent: generalPurpose]**
  - [x] Verify: existing `tests/test_exclude_headless.py` / `tests/test_exclude_headless_synthesis.py` Claude cases still pass; contract test fails until all adapters stub the method (or stubs land in this slice as `return False` with Claude correct). Delete any ephemeral verify artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Cursor Agent CLI headless detection**
  - [x] In `cursor_cli`, implement `is_headless_session` using store meta: headless when `subagentInfo` is present **or** `approvalMode` is `auto-review`; interactive top-level Agent sessions stay not headless. Persist useful audit fields when present. Cover filter-off. Note precedence vs `include_subagents` in code/docs comment as required by tech spec. **[Agent: generalPurpose]**
  - [x] Verify: unit/integration tests for the three Cursor meta shapes + convert skip/include; run focused pytest; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 3: Every other adapter implements `is_headless_session`**
  - [x] Implement the method on `codex_cli`, `opencode`, `openclaw` (always `False`; short code comment that dreaming is outside the session store), `copilot_cli`, `copilot_chat`, `chatgpt`, `gemini_cli`, `cursor` (IDE), `obsidian`, and any other registered adapter. Research store/fixtures during implementation; map only verified markers, otherwise `False`. Lock each rule with tests. **[Agent: generalPurpose]**
  - [x] Verify: registry walk shows all adapters implement the method; per-adapter tests green; focused pytest; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 4: Docs support map, docs-currency gate, CHANGELOG / UPGRADING**
  - [x] User-facing docs: support map + per-source “automated” meaning; OpenClaw = all sessions not headless; Cursor Agent CLI vs IDE (#2); today’s `--adapter` opt-in (#182). Grep user-facing docs (**exclude** `CHANGELOG.md`, `docs/UPGRADING.md`, and similar history) for adapter names and remove stale “stub” / “will be supported in v…” claims so only current support state remains. Add CHANGELOG + UPGRADING re-sync note. Add automated docs-currency check (test or script invoked by tests) as specified in tech. **[Agent: generalPurpose]**
  - [x] Verify: docs-currency check fails on a planted stale phrase and passes on the cleaned tree; spot-check support map; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 175-exclude-headless-adapters` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
