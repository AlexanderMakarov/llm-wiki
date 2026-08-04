# Tasks: Drop the entity-type taxonomy, make Project a page kind, unify wiki search

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md) · Issue [#102](https://github.com/AlexanderMakarov/llm-wiki/issues/102)

**Gates for every Verify task:** `ruff check llmwiki tests scripts` and `env -u LLMWIKI_ROOT python3 -m pytest tests/ -q`.
`LLMWIKI_ROOT` must be unset for test runs — exported, it redirects the suite at the operator's live vault.
**Never mutate the operator's live vault.** Any task needing a vault builds one under a tmp directory.

---

- [x] **Slice 1: The entity-type label stops being enforced**

  > After this slice, a page carrying any `entity_type` value — or none — lints clean, and asking for a rule that does not exist fails loudly instead of silently passing. Project pages still declare `type: entity` (valid), so the vault stays runnable.

  - [x] Delete `ENTITY_TYPES` and `validate_entity_type()` from `llmwiki/schema.py`. Leave `ENTITY_KIND_AI_MODEL`, `is_model_entity()` and `parse_model_profile()` untouched — `entity_kind` is a different, live field driving the AI-model index. **[Agent: general-purpose]**
  - [x] In `llmwiki/lint/rules/frontmatter_validity.py`, remove the `ENTITY_TYPES` import and the `entity_type` validation block. Leave `VALID_TYPES` alone for now (Slice 2 extends it). **[Agent: general-purpose]**
  - [x] Delete `llmwiki/lint/rules/entity_consistency.py` and remove its import line and numbered docstring entry from `llmwiki/lint/rules/__init__.py`. Import order fixes `REGISTRY` enumeration order — remove the one line, do not reorder the rest. **[Agent: general-purpose]**
  - [x] In `llmwiki/lint/__init__.py`, validate `selected` rule names against `REGISTRY` in `run_all()` before the loop; an unknown name must raise rather than silently skip. Surface it in `llmwiki/cli.py` as a non-zero exit naming the unknown rule and listing valid ones. **[Agent: general-purpose]**
  - [x] Update `docs/reference/reader-api.md` — remove the `entity_type` field from the sample payload, the facet block, and invariant #6 — and update `tests/test_reader_api_doc.py`, which imports `ENTITY_TYPES` at module scope and fails to import once it is gone. **[Agent: general-purpose]**
  - [x] Update `tests/test_schema_entity_types.py` and `tests/test_lint_rules.py` to the new behaviour; add cases for an arbitrary `entity_type` value linting clean, an entity page without the field linting clean, and an unknown `--rules` name exiting non-zero. **[Agent: general-purpose]**
  - [x] Verify: build a tmp vault containing an entity page with `entity_type: banana`, one with no `entity_type`, and one previously-promoted candidate; run `llmwiki lint` and confirm zero issues mentioning the field; run `llmwiki lint --rules entity_consistency` and confirm a non-zero exit naming the unknown rule. Run both gates. Delete the tmp vault afterwards. **[Agent: general-purpose]**

- [x] **Slice 2: Project is a first-class page kind**

  > After this slice, project pages declare what they are, are accepted by lint, and keep their claim checking and graph ranking. New project stubs carry no `entity_type`.

  - [x] Add `"project"` to `VALID_TYPES` in `llmwiki/lint/rules/frontmatter_validity.py`. **[Agent: general-purpose]**
  - [x] Change `ensure_project_stubs()` in `llmwiki/build.py` to emit `type: project` and drop the `entity_type: project` line. **[Agent: general-purpose]**
  - [x] Widen the `("entity", "concept")` gate in `llmwiki/lint/rules/claim_verification.py` to include `"project"`, so project pages keep being claim-checked. **[Agent: general-purpose]**
  - [x] In `llmwiki/graphify_bridge.py`, gate the `type_bonus` on kind ∈ {entity, concept, project} **and** a non-empty `file`. Synthetic project hub nodes already carry `type: "project"` with `"file": ""` — without the second condition this silently starts boosting navigational aggregates. **[Agent: general-purpose]**
  - [x] Migrate the tracked pages under `wiki/projects/*.md`: `type: entity` → `type: project`, drop `entity_type`. Frontmatter only — leave page bodies untouched. **[Agent: general-purpose]**
  - [x] Update `tests/test_project_stubs.py` (asserts `type: entity` + `entity_type: project`), `tests/test_reindex.py`, and any lint/graph tests encoding the old gate. Add a test that a project *page* receives the graph bonus and a project *hub* does not. **[Agent: general-purpose]**
  - [x] Verify: in a tmp vault, run `llmwiki build --seed-project-stubs` and confirm the new stub declares `type: project` with no `entity_type`; run `llmwiki lint` and confirm no invalid-kind error; confirm a project page appears in claim verification and the catalog still lists it under Projects. Run both gates. Delete the tmp vault afterwards. **[Agent: general-purpose]**

- [x] **Slice 3: Harvest stops guessing and stops stamping**

  > After this slice, candidate stubs carry no `entity_type`, and a run whose classification is incomplete stops with a cause-specific error instead of silently filing guesses as entities.

  - [x] Remove the `entity_type` line from `_stub_text()` in `llmwiki/candidates_harvest.py`. **[Agent: general-purpose]**
  - [x] Delete the post-write "N of M candidate(s) are filed as `entity_type: unknown`" warning. It counted every entity stub rather than ambiguous names — delete it, do not port it. **[Agent: general-purpose]**
  - [x] Make `run_harvest()` always fail closed on unclassified names: drop the `allow_unclassified` parameter and the branch it guards. The error must name the specific unclassified names, exit non-zero, and write nothing. **[Agent: general-purpose]**
  - [x] Distinguish the three failure causes in the error text: backend unreachable/unavailable; backend available but reply incomplete or unparseable (after the existing retry); source pages unreadable. Each must say what to fix and confirm nothing was written. **[Agent: general-purpose]**
  - [x] Tighten `write_stubs()`: keep the `entity` default only when `classify is None` (the explicit no-classifier mode); raise `ValueError` naming the offending names when a classifier was supplied but omitted them. **[Agent: general-purpose]**
  - [x] Remove `--allow-unclassified` from `llmwiki/cli.py` and its row from `docs/reference/cli.md`. **[Agent: general-purpose]**
  - [x] Update `tests/test_candidates_harvest.py`, `tests/test_cli_candidates_only.py`, `tests/test_synth_pipeline.py`; add cases for each of the three failure causes asserting a non-zero exit **and** an untouched candidates directory, plus the two `write_stubs` paths. **[Agent: general-purpose]**
  - [x] Verify: in a tmp vault, run synth with a stub classifier that labels everything — confirm stubs are written with no `entity_type` and no unknown-warning is printed; re-run with a classifier that omits a name and confirm a non-zero exit naming it with nothing written; confirm `--allow-unclassified` is absent from `--help`. Run both gates. Delete the tmp vault afterwards. **[Agent: general-purpose]**

- [x] **Slice 4: One search tool**

  > After this slice, agents see a single `wiki_search` that spans every page kind, narrows by kind, and ranks name matches first. `wiki_entity_search` is gone.

  - [x] Merge `tool_wiki_entity_search` into `tool_wiki_search` in `llmwiki/mcp/server.py`: accept `term` (required), `kind` (optional, one of `VALID_TYPES`), `include_raw` (optional). Delete the `wiki_entity_search` tool schema and implementation — no alias. **[Agent: general-purpose]**
  - [x] Compose `kind` with `include_raw`: `include_raw` selects whether `raw/sessions/` is scanned, `kind` filters frontmatter `type` in every corpus scanned (raw sessions carry `type: source`). A kind no raw file declares contributes nothing from the raw corpus — an empty contribution, not an error. **[Agent: general-purpose]**
  - [x] Emit page-level results: `path — title` with matching lines indented beneath. Pages matching by title or path sort above pages matching only in the body; within a group, sort by path for determinism. A title/path match with no body hit still returns its page. **[Agent: general-purpose]**
  - [x] Preserve the existing scan hardening — the single-terminator iteration with one shared hit cap (#413) and the aggregate byte budget with per-file cap and oversize-skip counter (#483). Use one aggregate cap for the merged tool, and keep reporting truncation and skipped-oversize counts. **[Agent: general-purpose]**
  - [x] Update `tests/test_mcp_enhanced.py` (its fixtures set `entity_type` on entity pages); extend rather than replace the existing cap/budget tests. Add cases for kind filtering, name-before-body ranking, and the four `kind` × `include_raw` combinations including the empty-raw-contribution case. **[Agent: general-purpose]**
  - [x] Verify: drive the MCP tool list and confirm exactly one search tool with no `wiki_entity_search`; run searches with and without `kind` against a tmp vault containing an entity, a concept and a project page, confirming narrowing, ranking, and composition with `include_raw`. Run both gates. Delete the tmp vault afterwards. **[Agent: general-purpose]**

- [x] **Slice 5: Facet, docs and release notes catch up**

  > After this slice, nothing in the codebase, docs, templates or examples teaches the field, and the release notes record every breaking change.

  - [x] Remove `entity_type` from `enrich_entry()`, `aggregate_facets()` and the `entity_types` parameter of `filter_entries()` in `llmwiki/search_facets.py`. This is inert at runtime — `enrich_entry` runs only over session entries, which never carry the field — so treat it as contract cleanup. **[Agent: general-purpose]**
  - [x] Sweep the remaining docs: `AGENTS.md` (schema section and the authoritative-frontmatter invariant), `docs/reference/reader-shell.md`, `docs/reference/ui.md`, `docs/tutorials/setup-guide.md`, `examples/obsidian-templates/entity-template.md` and its `README.md`, `examples/wiki_dashboard.md`, and `CLAUDE.md` if it names the field. Add `project` where page kinds are enumerated. **[Agent: general-purpose]**
  - [x] Add `CHANGELOG.md` entries recording four breaking changes: removed lint rule `entity_consistency`; removed CLI flag `--allow-unclassified`; removed MCP tool `wiki_entity_search` with `wiki_search` reshaped; new page kind `project`. **[Agent: general-purpose]**
  - [x] Update `tests/test_search_facets.py`, `tests/test_dashboard.py`, `tests/test_obsidian_templates.py`, `tests/test_edge_cases.py`, `tests/test_two_way_editing.py`. **[Agent: general-purpose]**
  - [x] Verify: grep the repository outside `raw/`, `site/` and vault page bodies for `entity_type` and confirm every remaining hit is intentional leftover metadata on existing pages, never an instruction to set or filter by it; confirm the built search payload has no `entity_type` facet key. Run both gates. Delete any scratch output afterwards. **[Agent: general-purpose]**

- [x] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 003-drop-entity-type-taxonomy` and `@regression` if suitable for long-term regression. Include the headline end-to-end case: against a **tmp vault**, sync → synth → promote every candidate → lint, asserting zero errors attributable to promotion. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–5 (all coding tasks) | Assigned to `general-purpose` — `context/product/hired-agents.md` records no Python/CLI specialist (template-generated agents were declined during `/awos:hire`) | Dispatch with the `modern-python-development` and `pytest-best-practices` skills; consider `/awos:hire` if a suitable registry agent appears |
| Slice 4 | Assigned to `general-purpose` — no MCP-protocol specialist exists in the registry | Accept for now; the change is contained to one server module with existing test coverage |
| Slice 6 | `testing-expert` expects the testing stack declared in `context/product/architecture.md`, which does not yet declare pytest/ruff | Pass the gate commands explicitly in the dispatch prompt; consider adding a testing section to `architecture.md` separately |
