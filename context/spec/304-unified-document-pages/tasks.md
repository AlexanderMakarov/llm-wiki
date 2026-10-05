# Tasks: Complete documents on one site page

- **Spec:** [`functional-spec.md`](functional-spec.md) · [`technical-considerations.md`](technical-considerations.md) — both Approved
- **Issue:** [#305](https://github.com/AlexanderMakarov/llm-wiki/issues/305)

**Standing constraints for every task.** Work only in the worktree `.claude/worktrees/feat-305-unified-document-pages` on branch `feat/305-unified-document-pages`. Vault-mutating commands target `$TMP_VAULT` (`.worktree-vault`) or an explicit `--out` under the scratchpad; never the operator's live vault. Always drive `python3 -m llmwiki` from the worktree, never PATH `llmwiki`. Gates before any slice is called done: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` (or the slice's targeted tests plus ruff on touched files). No new runtime deps. Do not rewrite `raw/` / `wiki/` / synthesis state (#311 out of scope).

---

- [x] **Slice 1: Logical document grouping (base-slug) + Recent/index consumers**

  > Fix `--project` collapse; one shared grouping API. App/build still runnable; Recent uses correct logical docs.
  - [x] Replace/extend `group_documents` in `llmwiki/raw_docs_site.py` with base-slug grouping within each directory; expose stable `id`, cleaned `title`, ordered `parts`, `folder_parts`, canonical `url`. Keep root-level singles. **[Agent: generalPurpose]**
  - [x] Wire Recent / home / raw intro consumers to the new grouping without changing storage. **[Agent: generalPurpose]**
  - [x] Unit tests: single-file; multi-chunk default layout; two distinct docs under one `--project` folder; cleaned titles. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/test_raw_docs_site.py -q` (and new grouping tests) pass; delete any ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Unified reading page + part URL stubs**

  > Opening a logical doc shows full assembled content; old `-NN` URLs stub to canonical `#` anchors.
  - [x] Implement unified HTML writer (assemble parts, strip part chrome/breadcrumbs, section anchors) and emit part stub pages (`meta` refresh + visible fallback link) for non-canonical part paths. **[Agent: generalPurpose]**
  - [x] Wire writer from `build_site` in `llmwiki/build.py`; keep sidebar mount + provenance behavior. **[Agent: generalPurpose]**
  - [x] Build-fixture tests: multi-part vault → one canonical HTML contains all part text; part URL is stub pointing at unified `#` anchor; single-file docs still render completely. **[Agent: generalPurpose]**
  - [x] Verify: targeted pytest green; optional `python3 -m llmwiki build --vault $TMP_VAULT` smoke; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 3: Search-index one entry per logical document + tree parity**

  > Ctrl+K and documents-tree share the same logical document leaves.
  - [ ] Change `build_search_index` document loop to emit one `type:"document"` meta entry per logical doc (cleaned title, canonical url, capped body). **[Agent: generalPurpose]**
  - [ ] Rebuild `documents-tree.json` leaves from the same logical docs (`id`/`label`/`href` + folder nesting); no per-chunk leaves. **[Agent: generalPurpose]**
  - [ ] Tests: search-index document set ≡ tree leaves (ids/titles/hrefs); multi-part doc is one palette entry. **[Agent: generalPurpose]**
  - [ ] Verify: pytest for index/tree parity green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 4: Documents sidebar filter (ancestors + highlight)**

  > Quick filter on doctree mount: starts-with then contains; keep ancestor folders; highlight substring; empty copy.
  - [ ] Add filter input UI + CSS in `llmwiki/render/js.py` / `css.py`; match/sort/filter tree; retain ancestors; `<mark>` highlight; empty state **No documents match**. Filter operates on tree leaves built from shared model (parity already tested). **[Agent: generalPurpose]**
  - [ ] JS/unit or build+DOM tests covering order, ancestors, highlight, empty copy (`file://`-safe patterns). **[Agent: generalPurpose]**
  - [ ] Verify: tests green; build throwaway vault and sanity-check Raw sidebar filter; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [ ] **Slice 5: Docs + CHANGELOG**

  > User-visible docs match behavior.
  - [ ] Update `CHANGELOG.md` `[Unreleased]`, `docs/reference/ui.md`, `docs/reference/reader-api.md`, and `docs/architecture.md` (and cli/mcp one-liner only if `--project` caveat needs it). **[Agent: generalPurpose]**
  - [ ] Verify: docs mention unified reader, shared catalog, filter UX; no personal vault paths. **[Agent: generalPurpose]**

- [ ] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 304-unified-document-pages` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
