# Product Roadmap: llm-wiki

_This roadmap outlines our strategic direction based on customer needs and business goals. It focuses on the "what" and "why," not the technical "how."_

_Backlog source of truth: open GitHub issues, plus migration/fork leftovers called out in the product definition. Cut/revive decisions are logged in [`docs/maintainers/DECLINED.md`](../../docs/maintainers/DECLINED.md) (and linked issues) so the same debate is not replayed._

---

### Phase 1 — Trust the product, then inventory the fork

_Stop misleading users; then systematically decide what fork residue to revive vs remove._

- [ ] **Honest pipeline reporting**
  - [x] **Honest "already synthesized" counts (#81):** Report corpus and synthesized totals in real units (eligible sources vs pages), not labels that imply `wiki/sources/` file counts when the number is state/union-based — same honesty on the Home pipeline widget.
  - [ ] **Honest `--estimate` candidate preview (#113):** Do not present a pre-synth candidate snapshot as if it forecasts the upcoming synth run.

- [ ] **Fork / migration residue cleanup (known)**
  - [x] **Drop hardcoded entity_type taxonomy (#102):** Stop validating the old seven-value enum that harvest stamps as `unknown` and then fails lint after promote.
  - [ ] **Fix broken docs links and link-check hygiene (#107):** Repair real 404s, exclude build-time placeholders, and make link-check fire on `main` so regressions do not wait for weekly cron. Close the duplicate auto-filed reports (#136, #152) against this one instead of accumulating a new issue per run.
  - [ ] **Dead `/vs/` comparison surface (#138):** `render_vs_section` has no production callers and hardcodes `REPO_ROOT/wiki`, so the model-comparison surface never renders — revive it or remove it per the inventory rule below.
  - [ ] **One project, one page (#126):** Project aggregation splits a single project across worktrees, clones, and adapters, so the same codebase appears as several projects.

- [ ] **Candidate review correctness**
  - [ ] **Harvest respects a dismissal (#146):** Stop re-proposing candidates the reviewer already discarded, and read the recorded `.reason.txt` instead of ignoring it.
  - [ ] **Merge resolves its own aliases (#139):** A merge records aliases but never resolves them, so every merge leaves broken `[[wikilinks]]` behind.
  - [ ] **Merge rewrites rather than stitches (#148):** Merging two topics concatenates their descriptions instead of producing one coherent description.
  - [ ] **Batch apply is order-independent (#149):** A batch that merges into a peer it also promotes or discards produces a different result depending on row order.

- [ ] **Operator privacy and test isolation**
  - [ ] **`llmwiki add` redacts the source path (#141):** The absolute source path is recorded unredacted, leaking the operator's home directory into the vault.
  - [ ] **Tests stop reading the developer's `config.json` (#142):** The suite picks up a gitignored local config, so personal settings can fail an otherwise-clean checkout.

- [ ] **Pipeline efficiency and recovery**
  - [ ] **Interrupted synth still harvests (#145):** Interrupting `synth` skips candidate harvest entirely and leaves the Home pipeline counters stale.
  - [ ] **One model call per source (#147):** Emit topics, kind, facts and description together instead of four separate synthesis calls.
  - [ ] **Per-vault lint rule scoping (#150):** Let the demo enforce warnings without inheriting rules that do not apply to it.

- [ ] **Migration inventory & keep/cut/revive log**
  - [ ] **Inventory what we inherited:** Catalog product surfaces left from the upstream fork and this fork's additions — CLI commands, adapters (core vs contrib), site/viewer features, docs claims, one-shot migrate-* tools, and anything half-removed or still advertised but broken — against the product definition's "cut useless / restore broken" goal.
  - [ ] **Decide and log each item:** For every inventoried surface, choose keep, revive (file/track a GitHub issue), or remove as useless; append removals and explicit non-goals to `docs/maintainers/DECLINED.md` with date + one-line reason (same format as existing entries), and keep revive work on the issue backlog.
  - [ ] **Execute cut/revive follow-ups:** Land the decided removals and restore-broken work as subsequent issues/PRs so the inventory does not become a static report.

---

### Phase 2 — Make the product self-explanatory

_Newcomers should understand benefits and the canonical loop without fork history or internal jargon._

- [ ] **Product-facing documentation**
  - [ ] **README as a product page (#109):** Lead with benefits and the finished wiki; one agent table (producer vs consumer, core vs contrib); no fork history at the top.
  - [ ] **CLI help as a lifecycle map (#112):** Every command says what it does and where it sits in sync → synth → review → build; mark migrate-* as maintenance.

- [ ] **Guided health check**
  - [ ] **`llmwiki doctor` (#110):** One read-only command that reports environment + vault health with the exact fix command for each finding.

---

### Phase 3 — Stronger browse; close the Cursor ingest gap

_Humans see knowledge on topic pages; Cursor becomes a real session source (product definition)._

- [ ] **Visual knowledge depth**
  - [x] **Topic pages show kind, freshness, and Key Facts (#108):** Entity/concept content reaches readers; project topics route to project pages; graph panel shows the same metadata.

- [ ] **Pages that read well**
  - [ ] **Synthesised page descriptions (#137):** Give entity, concept, and project pages a short description instead of leading with bare Key Facts.
  - [ ] **Projects index that ranks (#129):** Sort by recency, show freshness distribution, and mark which agent produced each project.
  - [ ] **Flip a trusted concept ↔ entity (#134):** Correct a mis-kinded page from the Candidates UI and CLI without a manual move.
  - [ ] **Update an already-ingested document in place (#151):** Re-ingest a changed source without duplicating its pages.

- [ ] **Cursor as a real session source**
  - [ ] **Parse Cursor session state (#2):** Stop silently filtering all Cursor sessions after discovering the store.

---

### Contributor enablement (parallel, not a product phase)

_Enables shipping the phases above from Cursor Agent; not an end-user product feature._

- [ ] **Cursor-compatible AWOS (#114):** Flat `/awos-*` commands, recruitment MCP, runtime tool mapping — so product→spec→implement works in this harness.

---

### Later / deferred

_Lower urgency or blocked on external reliability; revisit after Phases 1–3._

- [ ] **MCP protocol upgrade (#78):** Keep any-agent wiki consumption current with the 2026-07-28 (stateless core) MCP server model.
- [ ] **Claude Desktop Cowork / agent-mode ingest (#31):** Opt-in when the audit.jsonl path is solid.
- [ ] **claude.ai chat ingest (#32):** Explicitly deferred until a reliable export mechanism exists.

_Carried from the retired `docs/roadmap.md` (2026-08-16) — the only items from it with anything still to decide. Everything else there was shipped, covered by an open issue, or moved to [`docs/maintainers/DECLINED.md`](../../docs/maintainers/DECLINED.md)._

- [ ] **Eval framework — LLM-judged wiki quality (#154):** `llmwiki eval` does not exist as a subcommand, while `docs/maintainers/ROADMAP.md` lists an eval framework as shipped in v0.3. Decide whether to build it or correct the claim.
- [ ] **Timeline view of sessions:** A chronological browse surface. `llmwiki/changelog_timeline.py` is unrelated — it renders entity `changelog:` frontmatter, not sessions.
- [ ] **Session activity sparkline:** A per-session or per-project activity chart on the built site.
- [ ] **Hover-to-preview wikilinks:** Show the target page's opening lines on hover instead of requiring a click.
- [ ] **`/wiki-merge` — merge two vaults:** No design exists for slug collisions, duplicate sources, or conflicting `index.md` catalogs.
