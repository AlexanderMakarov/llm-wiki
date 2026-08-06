# Product Roadmap: llm-wiki

_This roadmap outlines our strategic direction based on customer needs and business goals. It focuses on the "what" and "why," not the technical "how."_

_Backlog source of truth: open GitHub issues, plus migration/fork leftovers called out in the product definition. Cut/revive decisions are logged in [`docs/maintainers/DECLINED.md`](../../docs/maintainers/DECLINED.md) (and linked issues) so the same debate is not replayed._

---

### Phase 1 — Trust the product, then inventory the fork

_Stop misleading users; then systematically decide what fork residue to revive vs remove._

- [ ] **Honest pipeline reporting**
  - [ ] **Honest "already synthesized" counts (#81):** Report corpus and synthesized totals in real units (eligible sources vs pages), not labels that imply `wiki/sources/` file counts when the number is state/union-based — same honesty on the Home pipeline widget.
  - [ ] **Honest `--estimate` candidate preview (#113):** Do not present a pre-synth candidate snapshot as if it forecasts the upcoming synth run.

- [ ] **Fork / migration residue cleanup (known)**
  - [x] **Drop hardcoded entity_type taxonomy (#102):** Stop validating the old seven-value enum that harvest stamps as `unknown` and then fails lint after promote.
  - [ ] **Fix broken docs links and link-check hygiene (#107):** Repair real 404s, exclude build-time placeholders, and make link-check fire on `main` so regressions do not wait for weekly cron.

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
