# Functional Specification: Honest already-synthesized counts on estimate and Home

- **Roadmap Item:** Honest "already synthesized" counts (#81)
- **Status:** Completed
- **Author:** implement-feature / product interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/81

---

## 1. Overview and Rationale (The "Why")

When someone runs a synthesize cost estimate, or looks at the Home Pipeline state table, they see totals labelled as if they were wiki source *pages* or *files*. Those numbers actually count **eligible inputs** for synthesis (sessions and documents that synthesize considers), including cases where the bookkeeping still says "done" even after a page was removed. On a mature vault the gap versus "how many markdown files are under wiki sources" can be dozens or hundreds of files, so the user looks for files that are not there and loses trust.

Separately, the estimate already has a convention that any figure which is a snapshot of the wiki *right now* (before this run) must be labelled as current or pre-run state — not as a forecast of the run being estimated. On-disk file counts are exactly that kind of snapshot.

Success looks like: estimate and Home never call the input totals "pages" or "files"; the Corpus line makes eligibility and session/doc split obvious; and both surfaces show **on-disk wiki/sources file counts** (CLI mix line + Home **On disk** column with Stubs) so the gap between "inputs marked done" and "pages that exist" is visible without implying a forecast.

Smoke feedback rejected an under-table note on Home — the On disk column replaces it.

---

## 2. Functional Requirements (The "What")

### 2.1 Estimate Corpus uses honest units

- When the user runs synthesize in estimate mode, the Corpus line must read: **Corpus: N eligible sources (S sessions + D docs)** (or wording the product treats as equivalent).
- N is the count of inputs eligible for synthesize (after the same eligibility rules a real synthesize run uses). S and D are the session and document parts of that total.
- The line must not invite comparison against an unfiltered raw-folder file listing without mentioning eligibility.

**Acceptance Criteria:**

- [x] Given a vault whose estimate reports non-zero Corpus, when the user runs synthesize in estimate mode, then the Corpus line includes the word **eligible** and shows session and doc counts in parentheses matching that total.
- [x] Given the same output, when the user reads the Corpus line, then it does not describe those numbers as pages under wiki sources.

### 2.2 Estimate Already synthesized uses honest units

- The Already-synthesized line must read: **Already synthesized: N of M eligible sources** (M matches Corpus).
- It must not say **pages in wiki/sources/** (or any wording that presents N as a file count under wiki sources).
- N remains the count of eligible inputs the estimate treats as already done (same meaning as today's number — only the label and framing change).

**Acceptance Criteria:**

- [x] Given a vault with some but not all eligible inputs already synthesized, when the user runs estimate, then Already synthesized appears as **N of M eligible sources** with M equal to the Corpus total.
- [x] Given the same output, when the user searches the Already-synthesized line for "pages in wiki/sources", then that phrase is absent.

### 2.3 Estimate reports source pages as current state (file counts)

- Estimate must print a separate line labelled as current state: **Source pages (current state): T on disk (Sess sessions + D docs + X stubs)** (append **+ O other** when uncategorized non-stub pages remain).
- T is how many `.md` files currently exist under `wiki/sources/` (excluding `_`-prefixed names). Sess / D / X are exclusive file-category subsets (stubs are not also counted under sessions or docs). Counts are **files**, not unique `source_file` keys.
- This line must not read as a forecast of what the upcoming synthesize run will write.

**Acceptance Criteria:**

- [x] Given a vault with at least one wiki source page on disk, when the user runs estimate, then a **Source pages (current state):** line appears with an on-disk file total and a sessions/docs/stubs mix.
- [x] Given a vault where pages were deleted by hand after earlier synthesis, when the user runs estimate, then the Already-synthesized input count and the Source pages current-state count may differ, and both remain labelled with their correct units so the gap is understandable.
- [x] Given estimate output, when the user reads the Source pages line, then it is explicitly marked current state (not as part of the estimated run's predicted writes).

### 2.4 Home Pipeline state matches the same honesty

- The Home Pipeline "files layer" caption and the Synthesized column must make clear that table cells count **eligible sources** (inputs), not files or pages — for Raw / To synthesize / Synthesized.
- The table itself stays input-based for those three columns: a document that was split into several wiki files still counts as one in Raw / To synthesize / Synthesized.
- The table gains an **On disk** column of wiki/sources **file** counts, attributed per agent (`detect_agent_label` when `source_file` starts with `raw/sessions/`), Documents (`raw/docs/` or `raw-doc` in tags), plus a **Stubs** row (On disk only; Raw / To synthesize / Synthesized show "—"). If uncategorized non-stub pages remain, add an **Other** row (On disk only).
- Do **not** show an under-table "Source pages (current state): …" note (smoke-rejected).

**Acceptance Criteria:**

- [x] Given a built Home page with Pipeline state data, when the user reads the files-layer caption and Synthesized header, then the wording indicates eligible sources (or equivalent), not "files" as the unit of the input columns.
- [x] Given a document that produced multiple part pages, when the user looks at the pipeline table, then that document still contributes 1 to the synthesized (or raw) input count — page fan-out is not expanded into the input columns.
- [x] Given Pipeline state with on-disk rows, when the user looks at the eligible-sources table, then they see an **On disk** column (including a **Stubs** row) and do **not** see an under-table Source pages note.

---

## 3. Scope and Boundaries

### In-Scope

- Relabeling Corpus and Already synthesized on synthesize estimate
- Adding the labelled current-state source-pages CLI line (file mix) on estimate
- Matching caption/column honesty on the Home Pipeline table, plus the On disk column / Stubs row
- Docs or help text that still describe those totals as page/file counts must be corrected in the same delivery
- Reusing the existing "current / pre-run state" labelling convention from the honest Candidates estimate work (#113)

### Out-of-Scope

- Per-file divergence lists (stale bookkeeping rows, on-disk-but-not-in-corpus, chunk fan-out details) behind a flag or collapsible
- A command or mode that reconciles or rewrites stale synthesize bookkeeping against disk
- Changing which inputs count as backlog versus done (stub eligibility and related backlog math stay as today)
- Honest Candidates estimate labelling (#113) — already delivered; only the shared labelling *convention* is reused here
- Other Phase 1 roadmap items (docs link hygiene, migration inventory, etc.)
