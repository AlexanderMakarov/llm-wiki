# Functional Specification: Trace wiki pages back to raw transcripts

- **Roadmap Item:** GitHub Issue #122 — expose the encoded chain from a wiki page down to its raw session material (defensible claims)
- **Status:** Approved
- **Author:** AWOS `/implement-feature` (issue #122)

---

## 1. Overview and Rationale (The "Why")

A synthesized wiki claim is only as valuable as the reader's ability to defend it. Today the chain from a high-level page down to the original session text is already recorded in page metadata, but no product surface follows that chain. A search that happens to hit both a wiki page and a transcript is coincidence, not provenance.

Concretely: someone reading a person or idea page who asks "where did this come from?" must open nested metadata by hand — first the list of source summaries, then each summary's pointer to a raw transcript.

**Desired outcome:** humans can click every listed Sources entry on the browsable site (preferring a built page, otherwise the raw file in a new tab). Operators and scripts can print the full downward chain with one command. Lint reports broken hops as errors; healing those problems is owned by `doctor` (#110), not this change.

**Success measures:**
- On topic and session/document pages, every Sources entry is a working link (HTML when available; otherwise raw, clearly marked, new tab).
- `llmwiki trace` prints the full downward chain (titles and locations; missing hops marked) without body excerpts.
- Lint fails with **errors** on broken provenance hops; docs point operators to #110 for guided fixes.

---

## 2. Functional Requirements (The "What")

### FR1 — Thin command-line helper prints the full downward chain

- **As an** operator or agent with shell access, **I want** a thin command that prints the chain from a wiki page to its source summaries and raw transcripts, **so that** I can verify provenance without opening nested metadata by hand.

The command accepts a page path or name. It prints the full downward chain: the starting page, each linked source summary, then each raw transcript those summaries point to. Each step includes a human-readable title and a location. It does not print transcript body excerpts. No new MCP tool is added; agents that only use MCP continue to use existing search (`include_raw` for term matches in raw text). Agents that can run CLI use this command for true link-following.

- **Acceptance Criteria:**
  - [ ] Given a higher-level wiki page that lists one or more source summaries, when I run the provenance command, then the output includes those source summaries with titles and locations.
  - [ ] Given those source summaries each point at a raw transcript, when I run the command, then the output also includes those raw transcripts with titles and locations.
  - [ ] Given a source-summary page that points at a raw transcript, when I run the command, then the output includes the raw transcript.
  - [ ] Given a successful trace, when I read the output, then it does not include transcript body excerpts — only titles and locations (and missing-hop markers per FR3).

### FR2 — Every Sources entry on the site is a clickable link

- **As a** reader on the static site, **I want** every Sources reference to open evidence in one click, **so that** I never stare at a dead label when the raw file still exists.

Links attach to the pages people already open: **topic pages** (browse surface for people/ideas/codebases) and **session / document pages**. For each Sources entry: prefer a built HTML page when one exists; otherwise link to the raw file, clearly marked as raw, opening in a **new browser tab**.

- **Acceptance Criteria:**
  - [ ] Given a topic whose backing wiki page lists Sources that have built HTML (session or document), when I open the topic page, then each such Sources entry is a working link to that HTML.
  - [ ] Given a Sources entry with no built HTML but an existing raw file, when I open the page, then that entry links to the raw file, is marked as raw, and opens in a new tab.
  - [ ] Given a session or document page with a matching wiki source summary and/or listed Sources, when I open it, then those entries follow the same prefer-HTML-else-raw(new-tab) rule.
  - [ ] Given a built page with no Sources information, when I open it, then no empty Sources section or broken placeholder appears.

### FR3 — Missing hops are visible, and the rest of the chain still appears

- **As a** person following provenance, **I want** broken links called out as missing, **so that** I know the chain is incomplete without losing the hops that still work.

- **Acceptance Criteria:**
  - [ ] Given a page that points at a source summary or raw transcript that no longer exists, when I run the provenance command, then that hop is marked missing rather than omitted.
  - [ ] Given a chain with one missing hop and other valid hops, when I run the command, then the valid hops still appear with titles and locations.
  - [ ] Given a missing hop, when I view the result, then the command does not treat the entire trace as failed solely because of that hop.

### FR4 — Any wiki page kind that carries provenance can be traced

- **As an** operator, **I want** provenance to work for every page kind that already records it, **so that** I do not have to remember which kinds are "special."

- **Acceptance Criteria:**
  - [ ] Given an entity, concept, project, topic, or other wiki page that lists source summaries, when I trace it, then those summaries appear in the chain.
  - [ ] Given a source-summary page with a raw-transcript pointer, when I trace it, then the raw transcript appears.
  - [ ] Given a page with no provenance metadata, when I trace it, then the result clearly indicates there is nothing to follow (not a crash, and not a fabricated chain).

### FR5 — Lint reports broken provenance hops as errors

- **As an** operator running vault health checks, **I want** the lint command to flag broken links from higher-level pages down through source summaries to raw files, **so that** incomplete provenance shows up as an error before I trust the wiki.

Lint inspects every wiki page that already carries provenance metadata. It walks the full downward chain: listed source summaries must resolve to real source-summary pages, and each summary’s raw-file pointer must resolve to an existing raw file. Each broken hop is reported as an **error**. Pages without provenance metadata are skipped.

Healing (suggested fix commands, pruning stale pointers, guided repair) is **not** implemented here — that belongs to `llmwiki doctor` (#110). This change documents that pointer for operators.

- **Acceptance Criteria:**
  - [ ] Given a higher-level page that lists a source summary that does not exist, when I run lint, then an error names that missing summary.
  - [ ] Given a source-summary page whose raw-file pointer does not exist on disk, when I run lint, then an error names that missing raw file.
  - [ ] Given a page with no provenance metadata, when I run lint, then this rule adds no issue for that page.
  - [ ] Given only valid provenance chains, when I run lint, then this rule reports no errors.
  - [ ] Docs for this rule tell the operator that guided repair will live under `doctor` (#110).

---

## 3. Scope and Boundaries

### In-Scope

- Shared provenance walker used by CLI and lint (and by build for link targets).
- Thin CLI `trace` (downward full chain; titles and locations; missing markers; no body excerpts).
- Site: every Sources entry is a link — prefer HTML; else raw marked “(raw)”, new tab — on topic and session/document pages.
- Lint rule: full-chain provenance integrity as **errors**; docs point to #110 for fixes.
- Support for any wiki page kind that already carries provenance metadata.

### Out-of-Scope

- New MCP tool for provenance (agents keep using existing `wiki_search` / `include_raw` for term search).
- Enriching search results with link-followed provenance.
- Upward tracing (from a raw transcript to every wiki page that cites it).
- Implementing `doctor` or automated heal/prune of broken provenance (#110).
- Compiling new dedicated HTML trees for entity/concept/wiki-source files.
- Large provenance panels or dashboards on the site.
- Including transcript body excerpts in trace output.
- Other roadmap / backlog items not named in this specification.
