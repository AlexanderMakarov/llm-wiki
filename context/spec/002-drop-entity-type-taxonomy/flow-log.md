# Flow log — 002-drop-entity-type-taxonomy (#102)

Resume state for `/implement-feature`. Newest entry last.

## 2026-08-04 — fetch-ticket

- Source: GitHub Issue [#102](https://github.com/AlexanderMakarov/llm-wiki/issues/102), state `OPEN`, no labels, one owner comment (scope add: MCP + docs).
- Referenced issues #137 (original taxonomy) and #90 (entity|concept classification) read as context only — no unreachable links.
- `TICKET_ID` = 102.

## 2026-08-04 — resume-detection

- No prior spec for #102; `context/spec/` held only `001-honest-estimate-candidates` (#113, merged as `c2c8768`).
- No open or merged PR for #102. Issue open. Fresh start, no resume.

## 2026-08-04 — workspace

- `context/product/architecture.md` readable. Working tree clean at start.
- `BRANCH` = `chore/102-remove-entity-type-taxonomy`, created from `origin/main` (`c2c8768`).
- Branch prefix is `chore/` rather than delivery-flow §2's `feat/`: the ticket is a `chore:` and the repo has precedent (`chore/114-awos-cursor`). Not treated as a flow defect.

## 2026-08-04 — specs (functional)

- Produced `context/spec/002-drop-entity-type-taxonomy/functional-spec.md`, Status **Approved** (user: "lgtm").
- Scope grew well past the issue text during the interview. Decisions taken, all by the maintainer unless noted:
  1. **Promote `project` to a first-class page kind** and ship it inside #102 (not split). Driver: `entity_type: project` turned out to be a workaround for `project` missing from the valid page kinds, so removing the field without promoting the kind would leave project pages indistinguishable from entities.
  2. **Migrate the 17 existing `wiki/projects/*.md` pages** in this repo's vault to `type: project`, dropping `entity_type`.
  3. **Merge both agent-facing search tools into one `wiki_search(term, kind?, include_raw?)`**; `wiki_entity_search` removed. Page-level results, name matches ranked first, `kind` + `include_raw` mutually exclusive. Rationale accepted: breaking the tool once beats renaming now and merging later.
  4. **Old tool names removed outright**, no deprecated aliases.
  5. **`--allow-unclassified` withdrawn** — synth fails closed on incomplete classification with a cause-specific error (backend unreachable / reply incomplete / sources unreadable).
  6. Assumptions recorded without objection: `entity_consistency` lint rule deleted; entity-type facet removed from browse drawer and reader summary; harvest classification stays binary entity|concept; no vault-migration command for other users.
- Findings from code that shaped the spec (carry into tech):
  - `entity_type: unknown` is stamped on **every** entity candidate, not just unclassified ones (`candidates_harvest.py:220`, `kind` derived from folder at `:266`) — verified empirically. The existing "N filed as unknown" warning (`:396-404`) is therefore already wrong, counting entity stubs rather than ambiguous names. Removing the flag deletes the warning rather than fixing it.
  - Real misclassification happens at `candidates_harvest.py:265`, where a name absent from the classifier reply silently defaults to `entity`. Independent of `entity_type`; addressed by R5's fail-closed behaviour.
  - Four sites key on `type == "entity"` and need attention when `project` becomes a kind: `frontmatter_validity.py:17` (`VALID_TYPES`), `claim_verification.py:24` and `graphify_bridge.py:475` (both gated to `("entity","concept")` — project pages silently drop out if missed), `mcp/server.py:1191`.
  - `entity_kind: ai-model` (`schema.py:42`, model index) is a **different live field**, one character from `entity_type`. Fenced off as out-of-scope.

- **Next stage:** `/awos:tech` → `technical-considerations.md` (approval gate before `/awos:tasks`).

## 2026-08-04 — specs (technical)

- Produced `context/spec/002-drop-entity-type-taxonomy/technical-considerations.md`, Status **Approved** (user: "lgtm").
- Exploration was not re-delegated to `Explore`: the code survey was already complete and verified during the spec interview, and `/implement-feature` forbids re-deriving established facts. Findings are recorded in the previous entry and in the tech spec itself.
- Technical decisions taken in the tech stage (beyond transcribing the functional spec):
  1. **Unknown lint rule names must exit non-zero.** `run_all()` silently skips names not in `REGISTRY`, so `lint --rules entity_consistency` post-deletion would run zero rules and report a clean vault. Validation added for all rule names — closes a pre-existing silent-pass hole, required by R1's fourth criterion.
  2. **Graph bonus gates on kind AND non-empty `file`.** `graphify_bridge` synthesises project *hub* nodes already carrying `type: "project"` (`:168`, built with `"file": ""`), so widening the `("entity","concept")` tuple alone would silently boost navigational aggregates. Real pages carry a path; hubs do not.
  3. **`write_stubs` raises when a supplied classifier omitted names**, and keeps the `entity` default only when `classify is None` (the explicit no-classifier test mode). Removes the silent misfiling path that survives `run_harvest` failing closed.
  4. **Merged search uses one aggregate cap** replacing the 200 (grep) / 50 (entity) split, preserving the #413 single-terminator scan and #483 aggregate byte budget as preserve-don't-re-derive constraints.
- Additional finding: the `entity_type` facet is already inert at runtime — `enrich_entry` has one call site (`build.py:2477`) over *session* entries only, whose frontmatter never carries the field, so `_facets["entity_type"]` is always `{}`. `drawer-browse` is a static prototype (`prototypes.py`, #114), not a live faceted UI. R6 is therefore contract cleanup with no behavioural change.
- Specialist gap confirmed: no Python/CLI or MCP agent in `hired-agents.md`; implementation falls back to `general-purpose` plus `modern-python-development` / `pytest-best-practices` skills, with `testing-expert` for the acceptance slice.

- **Next stage:** `/awos:tasks` (no approval gate) → `/awos:implement`.

## 2026-08-04 — tasks

- Produced `context/spec/002-drop-entity-type-taxonomy/tasks.md`: 6 slices, 33 tasks. No approval gate per delivery-flow §4.
- Slice shape (vertical, each leaving the vault runnable):
  1. Label stops being enforced (schema + frontmatter_validity + delete `entity_consistency` + unknown-rule validation + reader-api doc/test).
  2. `project` becomes a page kind (VALID_TYPES, build stubs, claim_verification, graph bonus, 17-page migration).
  3. Harvest stops stamping and fails closed (stub text, warning deleted, cause-specific errors, `write_stubs` strictness, CLI flag removal).
  4. Merged `wiki_search` with `kind` filter; `wiki_entity_search` deleted.
  5. Facet removal + docs sweep + CHANGELOG breaking entries.
  6. Feature Testing & Regression (`testing-expert`), including the headline tmp-vault sync → synth → promote-all → lint case.
- Slices 1 and 2 both touch `frontmatter_validity.py`, and 1 and 2 both touch `build.py` — sequential slices in one branch, so they land together in the change request as tech spec §1 requires.
- All coding tasks assigned `general-purpose` (no Python/CLI or MCP specialist available); recorded in the Recommendations table.

- **Next stage:** Step 5 commit-specs, then `/awos:implement`.
