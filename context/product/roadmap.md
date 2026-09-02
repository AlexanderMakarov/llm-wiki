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
  - [x] **Fix broken docs links and link-check hygiene (#107):** Repair real 404s, exclude build-time placeholders, and make link-check fire on `main` so regressions do not wait for weekly cron. Close the duplicate auto-filed reports (#136, #152, #157, #194) against this one instead of accumulating a new issue per run.
  - [x] **Dead `/vs/` comparison surface (#138):** Removed — `llmwiki/compare.py`, `render_vs_section`, vs CSS, docs/nav claims, and tests are gone. `/models/` and the ai-model schema stay.
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
  - [x] **Interrupted synth still harvests (#145):** Interrupting a sources pass drains in-flight work, then harvests candidates from pages already written (unless `--sources-only`); `build` refreshes Home `on_disk` when stored totals disagree with disk.
  - [x] **One model call per source (#147):** Each `synth` run prepares known-names once, then summarises each queued source once (kind, facts, and description on Connections); harvest and promote are offline parsers.
  - [x] **Per-vault lint rule scoping (#150):** Let the demo enforce warnings without inheriting rules that do not apply to it.

- [ ] **Migration inventory & keep/cut/revive log**
  - [ ] **Inventory what we inherited:** Catalog product surfaces left from the upstream fork and this fork's additions — CLI commands, adapters (core vs contrib), site/viewer features, docs claims, one-shot migrate-* tools, and anything half-removed or still advertised but broken — against the product definition's "cut useless / restore broken" goal.
  - [ ] **Decide and log each item:** For every inventoried surface, choose keep, revive (file/track a GitHub issue), or remove as useless; append removals and explicit non-goals to `docs/maintainers/DECLINED.md` with date + one-line reason (same format as existing entries), and keep revive work on the issue backlog.
  - [ ] **Execute cut/revive follow-ups:** Land the decided removals and restore-broken work as subsequent issues/PRs so the inventory does not become a static report.
  - [x] **Eval framework: build it or drop the claim (#154):** Claim dropped — `llmwiki eval` was never implemented; remaining docs no longer advertise it. Wiki quality stays `llmwiki lint` / `/wiki-lint`.

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
  - [ ] **Hover-to-preview wikilinks:** Show the target page's opening lines on hover instead of making the reader click through to find out whether it is worth reading. Advertised as shipped in v0.2; never built.
  - [ ] **Timeline view of sessions:** A chronological browse surface over the corpus. Also advertised as shipped in v0.2 and never built — `llmwiki/changelog_timeline.py` is unrelated, it renders entity `changelog:` frontmatter.
  - [ ] **Session activity sparkline:** A compact per-project activity chart so a reader can see cadence without opening the analytics page.

- [ ] **Pages that read well**
  - [ ] **Synthesised page descriptions (#137):** Give entity, concept, and project pages a short description instead of leading with bare Key Facts.
  - [ ] **Projects index that ranks (#129):** Sort by recency, show freshness distribution, and mark which agent produced each project.
  - [ ] **Flip a trusted concept ↔ entity (#134):** Correct a mis-kinded page from the Candidates UI and CLI without a manual move.
  - [ ] **Update an already-ingested document in place (#151):** Re-ingest a changed source without duplicating its pages.

- [ ] **Cursor as a real session source**
  - [ ] **Parse Cursor session state (#2):** Stop silently filtering all Cursor sessions after discovering the store.

---

### Phase 4 — v1.0 stability pass

_No new features. Lock what exists so users can depend on it._

- [ ] **API freeze:** CLI flags, frontmatter schema, and slash-command contracts stop changing without a migration note; breaking changes wait for a major.
- [ ] **LTS branch:** v1.x receives security fixes for 12 months after v1.0.
- [ ] **Docs polish:** every shipped feature documented and every tutorial current — with the claims verified against the code. Hover-preview and a timeline view were advertised as shipped and never built; the false eval-framework claim is already dropped (#154).

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
- [ ] **`/wiki-merge` — merge two vaults:** Deferred for want of a design: no answer yet for slug collisions, duplicate sources, or two `index.md` catalogs that disagree.
