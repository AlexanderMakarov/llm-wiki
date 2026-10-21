# Functional Specification: Refresh the competitor landscape page and keep the example vault in sync

- **Roadmap Item:** [#220](https://github.com/AlexanderMakarov/llm-wiki/issues/220) — Demo corpus still ships competitor-landscape content after the doc was removed *(ticket premise corrected: the page was never removed from `main`; deliver an update + demo refresh instead)*
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

Readers who open the competitor landscape documentation should see current facts about what llmwiki is, which agents it supports, and when another tool is a better fit. The page on `main` is behind the product (adapter count, Python baseline, page-kind wording). A fresher draft already exists as maintainer scratch; promoting those corrections into shipped docs — then refreshing the example vault so its ingested copy matches — is the intended outcome.

The original ticket assumed the page had already been removed. That removal never landed. Success for this work is an accurate, still-shipped comparison page and an example vault that mirrors it, not deletion.

## 2. Functional Requirements (The "What")

1. **The competitor landscape documentation page is current.**
   - A reader sees an accurate picture of llmwiki’s agent coverage, runtime baseline, and positioning relative to the compared tools.
   - Wording that still describes retired page kinds or outdated dependency claims is corrected.
   - The documentation index continues to link to this page.
   - **Acceptance Criteria:**
     - [ ] Given the competitor landscape page after this change, when a reader checks the multi-agent and runtime rows / positioning bullets, then they match the product’s current adapter set and Python/`markdown` dependency baseline (not the old “six agents” / “3.9+ zero deps” claims).
     - [ ] Given the documentation index, when a reader looks for Competitor landscape, then the link is present and opens the updated page.

2. **The comparison table holds only the closest, still-active peers. Other live tools get a short note under the table. Stale tools leave the page.**
   - “Still active” means a public product change in the last month (checked 2026-10-21; window from 2026-09-21).
   - The table is a function grid. Each row is a capability. Each column is a tool: this project, [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki), and the [Karpathy LLM Wiki Obsidian plugin](https://community.obsidian.md/plugins/karpathywiki). A reader can see, row by row, what each tool takes in, what it produces, and where they use it.
   - Because the other project is also named llmwiki, the column heading names the author (lucasastorian) so the two columns are not confused. That heading is not a substitute for the function rows.
   - Under the table, one short functional paragraph each for tools that are active but solve a different job: [mem0](https://github.com/mem0ai/mem0), [agentmemory](https://github.com/rohitg00/agentmemory), and [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory). Each paragraph says what function that tool provides (who remembers what, and for whom) and how that differs from compiling a wiki a person browses. No second feature grid.
   - Rewind / Limitless and Pieces are removed. Rewind’s screen recorder was shut down in December 2025. Pieces’ last listed product update is May 2026. The “manual notes” column is removed; a single sentence under “when this is not the right tool” may still say that writing notes by hand is enough when there are few sessions.
   - Claims stay at product shape. Marketing numbers from those projects’ READMEs are not copied in as facts.
   - **Acceptance Criteria:**
     - [ ] Given the comparison table, when a reader lists the columns, then they are this project, lucasastorian/llmwiki, and the Obsidian Karpathy LLM Wiki plugin — and not Rewind, Pieces, mem0, agentmemory, or TencentDB.
     - [ ] Given the page below that table, when a reader looks for mem0, agentmemory, and TencentDB Agent Memory, then each has a short description and a link, and none of them has a column in the table.
     - [ ] Given the page, when a reader searches for Rewind, Limitless, or Pieces, then those products are not presented as current alternatives.
     - [ ] Given the lucasastorian column, when a reader compares it with this project’s column, then at least the rows for inputs, output, where you read it, and what runs it differ in substance — the heading alone is not the comparison.

3. **The example vault mirrors the updated page.**
   - After a demo refresh driven by the docs change, the example vault’s raw competitor parts and derived wiki pages reflect the updated content (or are regenerated consistently from it).
   - Catalog counts and cross-links that involve those sources stay coherent.
   - **Acceptance Criteria:**
     - [ ] Given the committed example vault after this change, when a maintainer inspects the competitor-landscape raw/wiki material, then it corresponds to the updated documentation page (no dangling “page was deleted” provenance story).
     - [ ] Given `llmwiki lint` against the example vault, when the check finishes, then it reports no new broken links or orphans caused by this refresh.

4. **Getting-started describes the current session file layout.**
   - The short sync comment no longer implies per-project subfolders under the sessions directory.
   - **Acceptance Criteria:**
     - [ ] Given getting-started’s three-commands section, when a reader reads the sync line’s path hint, then it describes flat session files under the sessions directory (not `<project>/*.md` subfolders).

## 3. Scope and Boundaries

### In-Scope

- Updating `docs/competitor-landscape.md`: refresh our own facts; comparison table is this project plus lucasastorian/llmwiki and the Obsidian Karpathy LLM Wiki plugin; short notes under the table for mem0, agentmemory, and TencentDB Agent Memory; drop Rewind/Limitless, Pieces, and the manual-notes column.
- Keeping the docs-index link to that page.
- Refreshing the example vault so competitor raw/wiki material matches the updated doc.
- Updating the getting-started sync path hint to flat session naming.
- CHANGELOG / release-note line for the user-visible docs (and demo) change.
- Closing #220 with this corrected delivery (page kept and refreshed; demo consistent) — not with removal.

### Out-of-Scope

- Removing the competitor landscape page from product docs or the example vault.
- Reviving the old `/vs/` comparison site surface (#138 / DECLINED).
- A full release-day demo session regenerate unrelated to this docs change.
- Copying star counts, recall percentages, or other marketing stats from those projects’ READMEs into the page.
- A full competitive teardown or benchmark of the four systems.
