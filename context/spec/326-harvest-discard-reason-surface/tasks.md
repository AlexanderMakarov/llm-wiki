# Tasks: Surface prior discard reasons for near-match candidates (#146)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** Completed

---

- [x] **Slice 1: `dismissals.json` ledger — sole runtime source of truth**

  > After this slice, discard/merge update `wiki/archive/candidates/dismissals.json` only (no new `*.reason.txt`); `discarded_names` / `merged_intents` read the ledger; migrate rebuilds from legacy reason files.

  - [x] Create `llmwiki/dismissal_ledger.py` as the **sole** owner of `dismissals.json` I/O: versioned schema with `dismissals[]` + `merges[]`, atomic save, `upsert_dismissal` / `upsert_merge`, `iter_dismissals` / `iter_merges`, `rebuild_ledger_from_archive` (import legacy sibling `*.reason.txt`). No other module may open that path. **[Agent: python-pro]**
  - [x] Rewire `discard` / `merge` in `llmwiki/candidates.py`: archive stub as today, then ledger upsert; stop writing new sibling `*.reason.txt`. Reimplement `discarded_names` / `merged_intents` as thin wrappers over ledger iterators (preserve call-site signatures for `topics.py` / migrate). **[Agent: python-pro]**
  - [x] Register `llmwiki migrate` subcommand to rebuild/import the ledger (`--dry-run`, idempotent); auto-rebuild when ledger missing on first ledger read if that matches tech (document choice in module docstring). Point `migrate_discarded_topic_links` at ledger iterators instead of scanning reason files. **[Agent: python-pro]**
  - [x] Add `tests/test_dismissal_ledger.py` (+ extend `tests/test_candidates.py` / `tests/test_migrate_discarded_topic_links.py`): upsert, no new reason.txt after discard/merge, rebuild from fixtures, discarded_names/merged_intents agree with ledger, migrate dry-run. Run focused pytest + ruff. **[Agent: python-pro]**
  - [x] Verify: from worktree, focused pytest on ledger/candidates/migrate tests green; `ruff check` on touched Python; confirm a discard under `$TMP_VAULT` creates/updates `dismissals.json` and does not create a new `*.reason.txt`. Delete ephemeral verify artifacts. **[Agent: python-pro]**

- [x] **Slice 2: Near-match prior-dismissal on `candidates list` (CLI)**

  > Pending near-matches of dismissed names show the approved CLI mockup (reason or `(discarded without explanation)`).

  - [x] Add `llmwiki/candidates_near_match.py` (pure match + attach; **no** ledger file I/O — records from ledger helpers only). Threshold `0.90`, length floor, exact-key skip, merges excluded, best match only. **[Agent: python-pro]**
  - [x] Enrich `list_candidates` with `prior_dismissal`; format human `candidates list` and `--json` per approved mockups. **[Agent: python-pro]**
  - [x] Add `tests/test_candidates_near_match.py` + CLI/list assertions; run focused pytest + ruff. **[Agent: python-pro]**
  - [x] Verify: fixture vault — discard `Foobar` with reason, plant pending `FooBars` (true near-match; `FooBar`/`Foobar` fold equal via `norm_page_key`), `python3 -m llmwiki candidates list --vault $TMP_VAULT` shows indented prior-dismissal line; empty-reason `ApiClient`→`ApiClients` shows `(discarded without explanation)`. Delete ephemeral artifacts. **[Agent: python-pro]**

- [x] **Slice 3: Near-match mark on `candidates.html`**

  > Same `prior_dismissal` on site payload; Name cell muted secondary line per mockup.

  - [x] Extend `candidates_site` payload + Name-cell HTML; no browser-side matching. **[Agent: python-pro]**
  - [x] Extend `tests/test_candidates_site.py` for mark + `(discarded without explanation)`. Run focused pytest + ruff. **[Agent: python-pro]**
  - [x] Verify: build against `$TMP_VAULT`, assert `candidates.html` contains the Prior dismissal line for the fixture near-match. Delete ephemeral artifacts. **[Agent: python-pro]**

- [x] **Slice 4: Docs, CHANGELOG, UPGRADING, context note**

  - [x] Update `docs/reference/cli.md` (list output + migrate), `docs/reference/ui.md` (candidates page), `CHANGELOG.md` `[Unreleased]`, `docs/UPGRADING.md` (ledger + migrate), and a short `context/` AWOS note for the product PR. Prefer editing existing Unreleased entries when the surface is still unreleased. **[Agent: generalPurpose]**
  - [x] Verify: docs mention `dismissals.json`, migrate, and `(discarded without explanation)`; no personal vault paths. **[Agent: generalPurpose]**

- [x] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.

  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: [spec-directory]` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
