# Technical Specification: Drop the entity-type taxonomy, make Project a page kind, unify wiki search

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (Status: Approved)
- **Status:** Approved
- **Author(s):** AWOS `/implement-feature`
- **Ticket:** [#102](https://github.com/AlexanderMakarov/llm-wiki/issues/102)

---

## 1. High-Level Technical Approach

Five independent edits to the stdlib-only Python package, plus a docs/test sweep. No new dependencies, no new modules, no data store — the vault is files, so the "migration" is a committed diff over seventeen markdown pages.

1. **Delete the taxonomy.** Remove `ENTITY_TYPES` / `validate_entity_type` from `llmwiki/schema.py`, its enforcement in `frontmatter_validity`, and the `entity_consistency` rule that existed only to demand the field. Stop both writers (`candidates_harvest`, `build.ensure_project_stubs`).
2. **Promote `project` to a page kind.** Add it to `frontmatter_validity.VALID_TYPES`, extend the two `("entity", "concept")` gates that would otherwise drop project pages silently, and migrate the seventeen vault pages.
3. **Merge the two MCP search tools** into one `wiki_search` with a `kind` filter and page-level results, preserving the existing scan hardening.
4. **Make classification fail closed** — withdraw `--allow-unclassified`, replace the misleading warning with a cause-specific error.
5. **Sweep** facets, docs, templates, CHANGELOG, tests.

Ordering constraint: (1) and (2) touch the same two files (`frontmatter_validity.py`, `build.py`) and should land together. (3) and (4) are independent of each other and of (1)/(2).

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Schema and lint

| File | Change |
| --- | --- |
| `llmwiki/schema.py` | Delete `ENTITY_TYPES` tuple and `validate_entity_type()`. **Leave `ENTITY_KIND_AI_MODEL`, `is_model_entity()`, `parse_model_profile()` untouched** — `entity_kind` is a different, live field. |
| `llmwiki/lint/rules/frontmatter_validity.py` | Drop the `ENTITY_TYPES` import and the `entity_type` validation block. Add `"project"` to `VALID_TYPES`. |
| `llmwiki/lint/rules/entity_consistency.py` | Delete the file. |
| `llmwiki/lint/rules/__init__.py` | Remove the `entity_consistency` import and its numbered docstring entry. Import order is load-bearing (it fixes `REGISTRY` enumeration order) — remove the line, do not reorder the rest. |
| `llmwiki/lint/rules/claim_verification.py` | Widen the `("entity", "concept")` gate to include `"project"` so project pages keep being claim-checked. |

`frontmatter_completeness.REQUIRED` is `["title", "type"]` — it never required `entity_type`, so it needs no change.

**Unknown rule names must error (new behaviour, required by R1).** `run_all()` currently does `if selected and name not in selected: continue`, so `lint --rules entity_consistency` after deletion would run zero rules and report a clean vault — a silent false pass. Validate `selected` against `REGISTRY` before the loop and fail with the unknown name plus the list of valid rules. This applies to every rule name, not just the deleted one; it closes a pre-existing hole rather than adding a special case.

### 2.2 Project as a page kind

| File | Change |
| --- | --- |
| `llmwiki/build.py` (`ensure_project_stubs`) | Stub frontmatter becomes `type: project`; the `entity_type: project` line is dropped. |
| `wiki/projects/*.md` (17 files) | `type: entity` → `type: project`; drop `entity_type`. Committed diff, reviewable. |
| `llmwiki/graphify_bridge.py` | Extend the `type_bonus` gate — see below. |

**Graph ranking wrinkle.** `graphify_bridge` gives a `0.5` relevance bonus to nodes whose `type` is `entity` or `concept` ("prefer entity/concept pages over raw sources"). Wiki page nodes take `type` straight from frontmatter, so project pages currently qualify *as entities* and will stop qualifying the moment they declare `project`. But the graph also synthesises **project hub nodes** that already carry `type: "project"` — navigational aggregates, not pages. Naively adding `"project"` to the tuple would silently start boosting those hubs too, changing query results in a way nobody asked for.

Discriminate on the field that already separates them: synthetic hubs are built with `"file": ""`, real pages carry a path. Gate the bonus on kind ∈ {entity, concept, project} **and** a non-empty `file`. This both preserves today's ranking for entities/concepts and keeps hubs unboosted.

`candidates.py._TYPE_FOR_KIND` stays binary — candidates never produce projects (confirmed: harvest classification is entity/concept only). `reindex.py` already lists `projects` as a canonical catalog folder alongside `entities`/`concepts`, so the catalog needs no change.

### 2.3 Merged search tool (MCP)

Replace two tools with one. `wiki_entity_search` is deleted outright — no alias.

**Contract:**

| Field | Type | Notes |
| --- | --- | --- |
| `term` | string, required | literal case-insensitive substring, as today |
| `kind` | string, optional | one of `entity`, `concept`, `project`, `source`, `synthesis`, `comparison`, `question`, `navigation`, `context` — the `VALID_TYPES` set, matched against frontmatter `type` |
| `include_raw` | boolean, optional, default `false` | also scan `raw/sessions/` |

`kind` + `include_raw` together is a **request error** with an explanation (raw transcripts carry no page kind), not a silent precedence rule.

**Result shape** — page-level, replacing both the bare `file:line` list and the `[entity_type] path — title` list:

```
wiki/entities/Ruff.md — Ruff
  :14: Ruff replaced flake8 here
  :31: ruff check llmwiki tests
```

Pages whose **title or path** matches sort above pages matching only in the body; within each group, by path for determinism. A title/path match with no body hit still returns its page (with no context lines) — that is what preserves the old entity-search behaviour.

**Hardening to preserve, not re-derive.** The existing scan carries two fixes that must survive the merge: the single-terminator iteration with one shared hit cap (#413 — the old nested loops let `include_raw` return up to 2× the documented cap), and the aggregate byte budget with a per-file cap plus oversize-skip counter (#483). Keep one aggregate output cap for the merged tool rather than the old per-tool 200/50 split, and keep reporting truncation and skipped-oversize counts.

### 2.4 Fail-closed classification

| File | Change |
| --- | --- |
| `llmwiki/candidates_harvest.py` | `_stub_text` drops the `entity_type` line entirely. `run_harvest` loses the `allow_unclassified` parameter and always fails when `missing` is non-empty. The post-write "N filed as `entity_type: unknown`" warning is **deleted, not fixed** — it counted every entity stub, not ambiguous ones. |
| `llmwiki/cli.py` | Remove the `--allow-unclassified` argument. |
| `docs/reference/cli.md` | Remove its table row. |

**Error must distinguish three causes** (R5). `classify_names` currently collapses them: it returns `{}` both when the backend is unavailable and when the reply was unparseable, and source-read failures surface elsewhere. Distinguish at the call site:

| Cause | Signal available | Message must say |
| --- | --- | --- |
| Backend unreachable/unavailable | `backend is None`, or `is_available()` false/raising | which backend, that it was unreachable, and that nothing was written |
| Reply incomplete or unparseable | backend available but names absent from the result after the existing retry | the specific unclassified names, that the reply was incomplete, and that nothing was written |
| Source pages unreadable | read failure while harvesting targets | which paths failed to read, distinctly from a classifier problem |

All three exit non-zero and write nothing.

**`write_stubs` strictness.** `write_stubs` defaults an unclassified name to `entity` (`kinds.get(name, "entity")`). Once `run_harvest` fails closed, that default is unreachable from the CLI but still reachable from tests and any direct caller — a silent misfiling path with no remaining guard. Proposal: keep the default **only** when no classifier was supplied (`classify is None`, an explicit "don't classify" mode used by tests), and raise `ValueError` naming the offending names when a classifier *was* supplied but omitted them. That preserves the test-friendly path while removing the silent guess.

### 2.5 Facets

Remove `entity_type` from `enrich_entry`, `aggregate_facets`, and `filter_entries(entity_types=…)` in `llmwiki/search_facets.py`.

Note for reviewers: this is **inert at runtime today**. `enrich_entry` has exactly one call site (`build.py:2477`) and runs only over *session* entries, whose frontmatter never carries `entity_type`; so `_facets["entity_type"]` is already an empty dict in every built site. `filter_entries(entity_types=…)` has no caller. The change is contract cleanup, not behaviour change — and `drawer-browse` is a static prototype state, not a live faceted UI, so there is no client to update.

### 2.6 Docs and release notes

`AGENTS.md` (schema + invariants), `docs/reference/reader-api.md` (sample payload, facet block, invariant #6), `docs/reference/reader-shell.md` (column), `docs/reference/ui.md` (prototype description), `docs/reference/cli.md` (flag row), `docs/tutorials/setup-guide.md` (two examples), `examples/obsidian-templates/entity-template.md` + `README.md`, `examples/wiki_dashboard.md`, `CLAUDE.md` if it names the field.

`CHANGELOG.md` records four **breaking** changes: removed lint rule `entity_consistency`; removed CLI flag `--allow-unclassified`; removed MCP tool `wiki_entity_search` and reshaped `wiki_search`; new page kind `project`.

---

## 3. Impact and Risk Analysis

### System Dependencies

Lint registry · candidate harvest · site build (project stubs, search payload) · knowledge graph ranking · MCP server · Obsidian templates · reader-api doc contract test.

### Potential Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| **Silent coverage loss.** Project pages drop out of claim verification and graph ranking with no error — the change looks green while quality checks quietly stop covering seventeen pages. | Explicit acceptance criteria in R3; assert in tests that a `type: project` page is claim-checked and carries graph bonus. |
| **Graph hubs wrongly boosted** by a naive `"project"` addition, changing query results silently. | Gate on non-empty `file` as well as kind (§2.2); test both a project page and a synthetic hub. |
| **Confusing `entity_kind` with `entity_type`** — one character apart, and `entity_kind` drives the live AI-model index. | Named out-of-scope in the functional spec and §2.1; `tests/test_schema_entity_types.py` and the model-index tests must both still pass. |
| **Merged-search regression of #413/#483 hardening** — easy to lose when rewriting the scan. | §2.3 lists both explicitly; keep/extend existing cap and budget tests rather than rewriting them. |
| **`tests/test_reader_api_doc.py` imports `ENTITY_TYPES`** and asserts the doc's enum matches code — it fails at import once the constant is deleted. | Update the doc and the test together; drop the entity_type invariant assertion. |
| **Lint rule deletion breaks enumeration order** relied on by tests/consumers. | Remove only the one import line in `rules/__init__.py`; do not reorder. |
| **Vault migration touches committed pages** — a bad rewrite corrupts seventeen real pages. | Frontmatter-only edit (two lines per page); `llmwiki lint` over the vault after migration must be clean of new errors. |
| **Silent no-op on `--rules` typos** pre-exists and would mask the removed rule. | §2.1 adds validation; test that an unknown rule name exits non-zero. |

---

## 4. Testing Strategy

Gates: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`. **Run pytest as `env -u LLMWIKI_ROOT python3 -m pytest …`** — an exported `LLMWIKI_ROOT` redirects the suite at the operator's live vault in this checkout.

**Unit / behavioural, per requirement:**

- **R1** — a page with an arbitrary `entity_type` value lints clean; an entity page with none lints clean; `lint --rules entity_consistency` exits non-zero as an unknown rule.
- **R2** — a harvested candidate stub contains no `entity_type`; a seeded project stub contains none.
- **R3** — `type: project` passes `frontmatter_validity`; a project page is claim-checked; a project *page* gets the graph bonus and a project *hub* does not; the catalog still lists projects.
- **R4** — one search tool registered and no `wiki_entity_search`; unfiltered search spans kinds; `kind` narrows; title match outranks body-only match; `kind` + `include_raw` is refused; caps/budget behaviour preserved (extend existing tests, do not replace).
- **R5** — unreachable backend, incomplete reply, and unreadable sources each exit non-zero with their own message and write **nothing** (assert the candidates directory is untouched); no bypass flag in `--help`; a fully classified run writes stubs and prints no unknown warning; `write_stubs` raises when a supplied classifier omits a name, and still defaults when no classifier was supplied.
- **R6** — facet payload has no `entity_type` key; `filter_entries` no longer accepts the parameter.
- **R7** — `tests/test_reader_api_doc.py` and `tests/test_obsidian_templates.py` updated and passing.

**Existing tests requiring updates** (assertions encode the old behaviour): `test_schema_entity_types.py`, `test_lint_rules.py`, `test_mcp_enhanced.py`, `test_search_facets.py`, `test_candidates_harvest.py`, `test_reader_api_doc.py`, `test_dashboard.py`, `test_obsidian_templates.py`, `test_edge_cases.py`, `test_cli_candidates_only.py`, `test_project_stubs.py`, `test_reindex.py`, `test_synth_pipeline.py`, `test_two_way_editing.py`.

**End-to-end acceptance** (R1's headline claim) — against a **tmp vault**, never the operator's live vault: sync → synth → promote every candidate → `lint`, and assert zero errors attributable to promotion. This is the scenario the issue reports as always-failing, so it is the one that must be demonstrated green.

**Specialist gap:** `context/product/hired-agents.md` records no Python/CLI or MCP specialist agent (declined during `/awos:hire`), so implementation subagents fall back to `general-purpose` with the `modern-python-development` and `pytest-best-practices` skills. `testing-expert` covers the feature-level acceptance slice.
