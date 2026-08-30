# Tasks: Durable sync lookback (#192)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** Completed

---

- [x] **Slice 1: Resolve lookback from config + CLI**
  - [x] Add `llmwiki/sync/lookback.py` (or settings helper): parse `YYYY-MM-DD`; `resolve_effective_since(cli, config, adapter_name)` with precedence CLI → adapter date → adapter `"all"` → `filters.since` → None; invalid → raise/signal exit 2. Wire `convert_all` to resolve per adapter (CLI override still works). **[Agent: generalPurpose]**
  - [x] Verify: unit tests for precedence / `"all"` / empty inherit / absent unlimited / invalid; focused pytest green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Early prune + per-adapter sync report + hint**
  - [x] In `convert_all`: drop `ref.mtime < since_dt` before load; optional `discover_session_refs(since_dt=)`; Cursor filters headers when `since_dt` set; keep post-load `latest_record_time` gate; no `sync.files` write on lookback-only skip; per-adapter print after-early-filter → synced; end-of-run hint for `filters.since` / `adapters.*.since` / `configure-sources`. **[Agent: generalPurpose]**
  - [x] Verify: tests with fake refs/files prove early prune skips load and post-load still filters; report/hint smoke; focused pytest; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 3: Lookback GC for `sync.files`**
  - [x] After successful non-dry-run sync, for each adapter with effective `since_dt`, remove `sync.files` keys prefixed `f"{adapter}::"` whose stored mtime is before the lookback. Sources without lookback untouched; do not touch queue/synth/quarantine/ops. **[Agent: generalPurpose]**
  - [x] Verify: unit/integration test that old keys are removed and in-window keys remain; focused pytest; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 4: `estimate_sync_candidates` + configure-sources quiz**
  - [x] Add `BaseAdapter.estimate_sync_candidates()` default (eligible ≈ discovered; in_last_30_days by mtime); Cursor override via headers. Extend `configure_sources` quiz: shared start date first (Enter = today−30 / keep stored); per adapter facts (Sessions · Earliest · In last 30 days) → Enable → path → start date (Enter = inherit shared); merge-write without clobbering other keys. **[Agent: generalPurpose]**
  - [x] Verify: configure tests for Enter/date writes + estimate fakes; focused pytest; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 5: Docs, examples, CHANGELOG, UPGRADING**
  - [x] Document `filters.since`, `adapters.*.since` (`"all"`), inheritance, early prune, no state on lookback skip, GC, quiz keys/counts, sync hint. Update `examples/sessions_config.json`, configuration-reference (+ short related docs), CHANGELOG `[Unreleased]`, UPGRADING. Touch `context/` AWOS note as required for product PRs. **[Agent: generalPurpose]**
  - [x] Verify: greps/docs spot-check; ruff not required for md-only but run if py touched; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 177-sync-lookback` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
