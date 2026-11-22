# Tasks: Review possible duplicate curated pages (#365)

Spec: `context/spec/418-duplicate-page-review/` (functional + technical Approved).

- [ ] **Slice 1: Detect duplicate pairs + durable keep-distinct ledger**
  - [ ] Extract shared curated-fold helpers from `_keep_curated_names_on_their_pages`; add read-only `detect_duplicate_pairs(wiki_dir)` covering entities/concepts/projects; skip pairs in keep-distinct ledger. **[Agent: python-pro]**
  - [ ] Extend `dismissal_ledger.py`: `keep_distinct[]` coerce + `upsert_keep_distinct` / `iter_keep_distinct` / `is_keep_distinct_pair` (stable unordered `norm_page_key` pair key). **[Agent: python-pro]**
  - [ ] Tests: fold cases, undirected dedupe, project pages, skip keep-distinct, ledger upsert/idempotency/coerce — prefer `tests/test_duplicate_page_pairs.py` and extend `tests/test_dismissal_ledger.py` (no issue digits in filenames). **[Agent: python-pro]**
  - [ ] Verify: `ruff check` on touched paths; `pytest` on new/extended tests against `$TMP_VAULT` fixtures; delete ephemeral artifacts. **[Agent: general-purpose]**

- [ ] **Slice 2: Live `merge-pages` (no LLM)**
  - [ ] Implement `merge_pages(from, into)` — resolve live pages across kinds; survivor keeps kind; union sources/Connections; dated prose; Aliases; inbound wikilink rewrite; archive loser; `upsert_merge`; reconcile index. Do not reuse stub `merge()`. **[Agent: python-pro]**
  - [ ] Tests: same-kind merge, cross-kind merge, aliases, inbound links, archive + ledger merge row. **[Agent: python-pro]**
  - [ ] Verify: pytest for merge_pages; no LLM mocks required beyond unused; clean tmp vaults. **[Agent: general-purpose]**

- [ ] **Slice 3: Batch apply + Candidates list/CLI**
  - [ ] Extend `_VALID_ACTIONS` / `validate_candidate_batch` / `apply_candidate_actions` with `merge-pages` and `keep-distinct` (stubs unchanged; conflict rules per tech spec). Wire `cli.py` `candidates list` to print pairs (and JSON if applicable). **[Agent: python-pro]**
  - [ ] Tests: mixed stub + page-action batch validate/apply; list output includes pairs. **[Agent: python-pro]**
  - [ ] Verify: CLI apply on `$TMP_VAULT` fixture; ruff + pytest. **[Agent: general-purpose]**

- [ ] **Slice 4: Candidates.html “Possible duplicate pages” section**
  - [ ] Extend `candidates_payload` / `render_candidates_body` (+ JS collectActions) with duplicate-pair rows (titles, kinds, links, session counts, description, decisions) feeding the same Apply command. **[Agent: python-pro]**
  - [ ] Tests: payload/HTML contain section and action JSON shapes. **[Agent: python-pro]**
  - [ ] Verify: `python3 -m llmwiki build --vault "$TMP_VAULT"`; assert `site/candidates.html` contains section; delete ephemeral artifacts. **[Agent: general-purpose]**

- [ ] **Slice 5: Fixed curated titles in existing consolidation (no extra LLM call)**
  - [ ] Inject `<fixed_curated_titles>` + `<keep_distinct>` into consolidation prompt; deterministic post-process on `parse_and_cache` / `load_cache` to detach curated↔curated and keep-distinct folds; keep derive-time `_keep_curated_names_on_their_pages`. Update `topic_consolidation.md`. **[Agent: python-pro]**
  - [ ] Tests: prompt contains fixed titles; post-process undoes curated fold; keep-distinct honored; assert prepare still issues at most one synthesize call. **[Agent: python-pro]**
  - [ ] Verify: pytest topics_consolidate; ruff. **[Agent: general-purpose]**

- [ ] **Slice 6: Doctor, lint, agent-kit, docs**
  - [ ] Doctor check for pending duplicate pairs + `heal_kb.json` entry; new lint rule (not body-similarity `duplicate_detection`); update `agent_kit/commands/wiki-candidates.md`; CHANGELOG Unreleased + `docs/reference` rows as required. **[Agent: general-purpose]**
  - [ ] Tests/coverage for doctor id ⊂ KB, lint rule registration, reference coverage if applicable. **[Agent: python-pro]**
  - [ ] Verify: doctor/lint smoke on fixture vault; reference tests; ruff + targeted pytest. **[Agent: general-purpose]**

- [ ] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 418-duplicate-page-review` and `@regression` if suitable for long-term regression. Prefer `tests/test_duplicate_page_review_acceptance.py` (no issue digits in filename). **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
