# Tasks: Cursor IDE composer ingest (#2)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** In Progress

---

- [ ] **Slice 1: First-class `SessionRef` discovery (file adapters unchanged)**
  - [ ] Add `SessionRef` (`key`, `mtime`, `locator`) and `BaseAdapter.discover_session_refs()` with a default that wraps `discover_sessions()` + `path.stat()` / portable key. Update `convert_all` and `watch` to iterate refs (mtime + state key from the ref; pass `locator` into load/slug). No stub files. Keep file-backed adapters behavior-identical. **[Agent: generalPurpose]**
  - [ ] Verify: existing adapter/convert/watch tests still pass; add a focused unit test that a non-file `SessionRef` (non-existent locator) can drive mtime/state without `stat`. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 2: Local Cursor probe → synthetic fixture shape**
  - [ ] Read-only probe the operator’s Cursor `globalStorage/state.vscdb` (and workspace DB if needed): `cursorDiskKV` key shapes, bubble fields, archive flag, workspace association, spawned/parent markers. Write a short redacted field inventory under the spec dir (no personal content). Build synthetic in-test SQLite helpers matching that shape. **[Agent: generalPurpose]**
  - [ ] Verify: helper builds a minimal DB; inventory file has no absolute homes/usernames/transcript text. Delete ephemeral probe dumps outside the redacted inventory. **[Agent: generalPurpose]**

- [ ] **Slice 3: IDE discover / load / normalize (archived included)**
  - [ ] Rewrite `cursor` adapter: `discover_session_refs` from global `composerData:*`; `load_records` / `normalize_records` for bubbles; include archived; meta (`cursor_ide_meta`) with sessionId/timestamp; stop discovering bare `state.vscdb` as sessions. Wire platform global DB paths + workspace roots for association only. **[Agent: generalPurpose]**
  - [ ] Verify: unit tests for discover count, order, user/assistant normalize, archived kept same composer id; focused pytest green. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 4: Shared project slug with Agent CLI (#126 prep)**
  - [ ] Resolve workspace hash for IDE composers; emit `cursor-<hash[:12]>` (shared helper with `cursor_cli` if useful). Unmatched → `cursor-<composerId[:12]>`; no basename-only slug. Confirm hash alignment against local chats/`workspaceStorage` when available. **[Agent: generalPurpose]**
  - [ ] Verify: same hash string → identical slug from IDE helper and `cursor_cli`; unmatched fallback test; focused pytest. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 5: IDE headless (spawned vs user-facing)**
  - [ ] Implement `is_headless_session` for IDE using markers from Slice 2 probe; persist audit fields on meta; default `exclude_headless` skips spawned; filter-off includes them. If markers unconfirmed, document gap and keep honest `False` — do not invent fields. Update support-map / adapter docs for the locked rule. **[Agent: generalPurpose]**
  - [ ] Verify: interactive kept / spawned skipped / filter-off; #180 support-map test still distinguishes IDE vs CLI (wording may update). Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 6: Zero-parse warning + docs + CHANGELOG**
  - [ ] R6: one stderr warning when an adapter discovers ≥1 session and all yield empty after load/normalize/filter. Update `docs/adapters/cursor.md`, multi-agent support map / related pages, `CHANGELOG.md` `[Unreleased]`. Remove stale “scaffold / does not parse” claims for IDE ingest. **[Agent: generalPurpose]**
  - [ ] Verify: warning fires on empty-parse fixture and not when convert succeeds; docs grep clean of scaffold claims for current IDE behavior; focused pytest. Delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 176-cursor-ide-ingest` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
