# Flow log — 003-drop-entity-type-taxonomy (#102)

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

- Produced `context/spec/003-drop-entity-type-taxonomy/functional-spec.md`, Status **Approved** (user: "lgtm").
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

- Produced `context/spec/003-drop-entity-type-taxonomy/technical-considerations.md`, Status **Approved** (user: "lgtm").
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

- Produced `context/spec/003-drop-entity-type-taxonomy/tasks.md`: 6 slices, 33 tasks. No approval gate per delivery-flow §4.
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

## 2026-08-04 — implement

- All 35 tasks complete across 6 slices. Gates after every slice: `ruff check llmwiki tests scripts` clean, `python3 -m pytest tests/ -q` exit 0, each independently re-run by the orchestrator rather than trusted from the subagent report.
- **Dispatch deviation:** `/awos:implement` delegates one subagent per *task*; this run delegated one per *slice*. Deleting a shared symbol breaks every importer at once, so the smallest repo-runnable unit is "symbol deleted AND all importers updated". Per-task agents would each have reported success against a tree that could not import (`ENTITY_TYPES` breaks `frontmatter_validity` and, at module scope, `tests/test_reader_api_doc.py` + `tests/test_edge_cases.py`).
- **Interruption and recovery.** The Slice 4 agent died on an API spend limit immediately before running the suite; its edits were complete. The branch was then stashed (`wip: #102 … parked for feat/116`), `main` advanced by PR #121 (CI refactor) and `3971941` (AWOS flow regeneration), and the work was later restored intact from `stash@{0}` — 37 files, 933 insertions — with no loss.
- **Workspace moved to an isolated worktree** at `.claude/worktrees/chore-102-remove-entity-type-taxonomy`, rebased onto `origin/main` (`6c044e0`), with its own `config.json` pointing at a seeded throwaway `.worktree-vault`. This follows the regenerated §2 recipe. `.worktree-vault/` is untracked — stage explicitly, never `git add -A`.
- **Spec directory renumbered `002-` → `003-`.** `002-ci-refactor-ci` merged to `main` while this work was parked; index-by-max-plus-one gave both branches `002`. Internal references updated.
- **Live-vault incident (resolved).** Before the worktree move, a Slice 2 subagent ran a bare `python3 -m llmwiki build` and regenerated the operator's live `site/` at the configured vault. Vault *content* (`wiki/`, `raw/`) was untouched; only the regenerable artifact changed. Root cause: `LLMWIKI_ROOT` no longer exists (removed; `config_schedule.py` routes via `config.json` `vault.default_path`), so the `env -u LLMWIKI_ROOT` guard in the briefs was a no-op. Later briefs required `--vault "$PWD/.worktree-vault"`; the worktree makes it structural.
- **Sweep-planning defect worth carrying forward.** Slice file lists were built by grepping the field name, which misses two of three propagation axes. Every slice found files no slice owned: `docs/reference/cli.md` + `slash-commands.md` (rule *listing*), `docs/UPGRADING.md` (instructed the removed flag), `llmwiki/topics_page.py` (docstring), `llmwiki/usage.py` (`ENTITY_TOOLS` frozenset), and `examples/demo-usage/*` (public-demo fixture *data* naming a deleted tool, with a drifted `daily.json` aggregate).

## 2026-08-04 — verify

- All 30 acceptance criteria marked `[x]`; `functional-spec.md` and `technical-considerations.md` Status → **Completed**; `context/product/roadmap.md` #102 item ticked.
- Evidence: AC coverage matrix in `tests/test_102_acceptance.py` (7 acceptance tests, every AC mapped to a new or existing test), plus a real site build against `.worktree-vault` — 98 HTML files, `_facets` keys `['confidence','lifecycle','tags']`, and zero occurrences of `entity_type` anywhere in the output. Build artifacts and the seeded session were deleted afterwards.
- **R6-AC1 verified by data, not by rendering.** The criterion names a "browse panel"; `llmwiki/prototypes.py` (which emitted the `drawer-browse` state) no longer exists in the tree, so no such panel ships. Recorded as satisfied via the facet payload rather than a screenshot — no screenshot was taken and none is claimed.
- **RED validation is partial by nature here.** Genuinely executed for the headline, its RED companion, and project ranking (old logic copied as frozen local functions and shown to diverge on the same fixtures). Documented-not-executed for four tests (CLI unknown-rule, no-writer-stamps, old tool name, docs sweep) — confirmed against `git show HEAD:<path>` without running the old modules. Disclosed per test rather than claimed uniformly.
- **Pre-existing drift found, deliberately not fixed** (out of scope, worth separate issues): `docs/reference/reader-shell.md` documents `llmwiki/reader_shell.py`, which does not exist; `docs/reference/ui.md:174` documents the removed `drawer-browse` prototype; no test couples documented lint-rule listings to `REGISTRY`, which is why the rule-list drift went unnoticed.

- **Next stage:** smoke confirm, then dual local review (Step 8).

## 2026-08-04 — verify follow-up: `kind` + `include_raw` reversal

- The earlier decision recorded above ("`kind` + `include_raw` mutually exclusive") is **reversed**. Recorded as a new entry rather than an edit — the original was a real decision taken on a stated rationale, and the rationale being wrong is itself the record.
- **The rationale was factually false.** The tech spec asserted raw transcripts "carry no page kind". Raw session files under `raw/sessions/` declare `type: source` in frontmatter — confirmed across the operator's corpus (every sampled file of 807). The claim was never checked against a raw file; it sounded structurally obvious and passed both approval gates, implementation, and acceptance tests unchallenged, because each stage verified code-matches-spec rather than spec-matches-reality.
- **Corrected semantics:** `kind` filters on frontmatter `type:` wherever pages are scanned; `include_raw` selects whether the raw corpus is scanned at all. `kind=source` + `include_raw` returns wiki source pages and raw transcripts together; `kind=project` + `include_raw` returns project pages with an empty raw contribution — not an error.
- Code impact was one deleted early return: `_iter_scan_files` was already corpus-agnostic and already applied the kind filter to raw files via the canonical frontmatter parser. The refusal gated behaviour that already worked.
- Updated: `llmwiki/mcp/server.py` (refusal, tool + schema descriptions, docstring), `tests/test_mcp_enhanced.py` (refusal test replaced by four semantics tests), `tests/test_102_acceptance.py` (AC matrix), `functional-spec.md` R4 criterion, `technical-considerations.md` §2.3, `tasks.md` (a checked Slice-4 task asserted the refusal — a false record a later verify pass could have acted on), `CHANGELOG.md`.
- #413 (shared hit cap) and #483 (aggregate byte budget) coverage untouched and passing; byte accounting is unaffected because the budget decrement precedes the kind filter.
- Real link-following traceability (`entity → sources: → source page → source_file: → raw`) filed as **#122**, deliberately out of scope here.

- **Next stage:** dual local review (Step 8) on the corrected diff.

## 2026-08-04 — local review

- Dual review on the branch diff, both with no author-supplied focus areas.
  - Checklist review (governance docs + `REVIEW_CHECKLIST.md`): **request-changes** — 3 blockers, 8 nits, 4 questions.
  - Independent `code-reviewer`: **request changes** — 1 critical, 5 important, 8 notes.
  - Review files were kept **local at the operator's decision** and are deliberately not committed: `review.md`, `review-code-reviewer.md` under this directory.
- **The two reviews barely overlapped, which is the argument for running both.** The checklist review found policy failures (local MCP telemetry stageable from an untracked `.worktree-vault/`; a false "seventeen project pages" count in user-facing release notes). The independent reviewer found a product failure neither the checklist nor the orchestrator caught: `docs/UPGRADING.md` had no #102 section although `CLAUDE.md` directs users there before their first post-upgrade sync, and the ingest instructions still told agents to file projects as entity pages — which would have left the new page kind empty in exactly the agent-driven vaults this product targets.
- All findings accepted by the operator except four deferred-by-design items, which were also fixed on request. Applied in two sequential batches (docs/migration, then code) to bound spend-limit exposure after two earlier agent deaths.
- **Scope of the ingest-instruction fix was far wider than the finding suggested:** 9 actionable instructions across `CLAUDE.md`, `AGENTS.md`, `.claude/commands/wiki-ingest.md`, `.claude/skills/llmwiki-ingest/SKILL.md`, plus 5 descriptive claims in `wiki/entities/_context.md` (read by the Query Workflow), `docs/architecture.md`, `cheatsheet.md`, `faq.md`, and the quickstart. `AGENTS.md` was correct everywhere except one ingest step.
- **Correctness gap found in a criterion the orchestrator wrote.** The name-before-body ranking was a sort applied *after* the 200-line hit cap had already ended the walk, so a title match late in `rglob` order was never opened — worst-case exactly the `kind=source` + `include_raw` traceability path, where `wiki/sources/` is scanned before `raw/sessions/`. Fixed by collecting into separate name/body buckets so ranking is a property of collection; `_SEARCH_PAGE_CAP` added because a name-matched page renders as a bare header and so is not bounded by a line cap. RED-validated by restoring the old `break`; the test pins its own premise (asserts the name-match file is walked late) so it cannot pass for the wrong reason.
- **Two reviewer suggestions were rejected with reasoning, not silently.** (a) Bumping `ATTRIBUTION_VERSION` for the changed `hits` unit would make `load_rollup` collapse every historical rollup to unattributed — destroying more history than it documents; `hits` was kept in a stable unit instead. (b) Removing `wiki_entity_search` from `usage.ENTITY_TOOLS` was reverted: that set parses persisted historical records, not the live tool surface, so dropping a retired name silently relabels analytics a user has already read. The orchestrator had originally routed (b) as a "known miss" — the reviewer's reading was better.
- Deliberately not done: auto-re-stamping pre-existing project stubs (violates `ensure_project_stubs`' contract that user edits win; `UPGRADING` documents a `sed` recipe instead), and tombstoning the removed reader-api invariant slot (a "reserved" marker is the historical note this repo forbids; clients are now told to cite invariants by field rather than by list position).
- Also fixed: `llmwiki init` did not scaffold `wiki/projects/` although `reindex.CANONICAL_FOLDERS` lists it — a fresh vault had no home for the page kind the ingest instructions now require.
- Static gate green after both batches: `ruff check llmwiki tests scripts` clean, `python3 -m pytest tests/ -q` exit 0. Final size: 70 files, +1659/−838.
- Follow-up filed during this stage: **#122** (link-following traceability, `entity → sources: → source page → source_file: → raw`).

- **Next stage:** commit, rebase, push, open the change request.
