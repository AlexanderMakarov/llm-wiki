# Technical Specification: Curated knowledge reaches the browsing reader

- **Functional Specification:** [`functional-spec.md`](functional-spec.md)
- **Status:** Completed
- **Author(s):** 4ellendger
- **Issue:** [#248](https://github.com/AlexanderMakarov/llm-wiki/issues/248)

---

## 1. High-Level Technical Approach

Issue #248's headline is overstated: #108 already made `topics/<slug>.html` the browsable surface for entity and concept pages (`docs/reference/ui.md:223`), and on the demo vault 12 of 13 curated pages already have both a page and a correctly badged `⌘K` entry (`ui.md:313`). What is genuinely missing is one broken edge case, two absent browse affordances, and — the larger half — a site search that indexes and ranks nothing like the assistant's.

Five scoped changes, all in build layer **L2 Site** plus **L3 Viewer**:

| FR | Change | Where |
|---|---|---|
| FR1, FR2 | A curated entity/concept page always produces a topic node, however few sessions cite it | `llmwiki/topics.py` — opt-in parameter on `build_topic_graph` |
| FR1 | A vault with curated pages still gets topic pages when the graph is too sparse for the viewer | `llmwiki/build.py:3318-3453` |
| FR3 | Nav bar + mobile drawer gain a Topics entry | `llmwiki/build.py:885 nav_bar` |
| FR4 | `topics/index.html` groups entities / concepts / derived topics with counts | `llmwiki/topics_page.py:546-570` |
| FR7 | Site search mirrors `wiki_search` **match mode** over the wiki corpus, in two always-visible result groups | `llmwiki/build.py build_search_index`, `llmwiki/render/js.py` |

**FR2 needs no new entry type and no new entry key.** Once the node exists, the existing `type: "topic"` entry (`build.py:2775-2797`) is emitted with `kind` already run through `kind_label()`. `tests/test_108_acceptance.py::test_search_index_topic_entries_carry_only_the_frozen_keys` pins that key set — adding fields would break a deliberate guardrail, and a second entry type would put two palette rows behind one thing. Both rejected.

FR5 and FR6 are guarantees — see §3 and §4.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Why a curated page vanishes today (root cause)

Two functions in `llmwiki/topics.py` decide the node set, and neither consults the curated pages:

1. `derive_vocabulary` (`topics.py:128`) builds `Topic` objects purely from `[[wikilink]]` targets in `wiki/sources/**` — via `_session_pages` (`topics.py:68`), which is `scan_pages` (`llmwiki/graph.py:170`) filtered to `type == "sources"`. A curated page nothing links to produces **no `Topic` at all**.
2. `build_topic_graph` (`topics.py:287`) then applies `kept = [t for t in topics if t.count >= min_sessions]`, `min_sessions=2` (`topics.py:308`).

`topic_kind_lookup` (`topics.py:210`) — which knows every curated page — is called only *after* `kept` (`topics.py:366`), to decorate survivors.

Demo evidence, and it is worse than a drifted count: `demo/wiki/entities/Python.md` records three sources in frontmatter — `2026-05-25-csv-import-rounding`, `2026-06-07-pagination-cursors`, `2026-08-11-request-id-logging` — and **none of the three cites it**. The only page containing `[[Python]]` is a fourth, unrelated one (`2026-08-20-pdf-text-extraction`), confirmed under harvest's own case/punctuation folding (`norm_page_key`, the #204 rule), not just exact match. So `count == 1 < 2` and the page vanishes.

The page's recorded provenance and the live link graph are therefore **disjoint**: harvest at `min_refs=3` would not produce this page today, the graph at `min_sessions=2` discards it, yet it exists and is marked `status: reviewed`. This is the case for keying FR1 on *"a curated page exists"* rather than on any reference count — every count in the system already disagrees with the page's own record. (Whether the demo page's provenance is itself a data defect is a separate question, worth its own issue; it does not change what the site must render.)

### 2.2 Curated-page bypass (FR1, FR2)

Add an **opt-in** keyword to `build_topic_graph`:

```
build_topic_graph(wiki_dir, *, min_sessions=2, max_neighbors=12, similarity=…,
                  include_curated_pages: bool = False)
```

When true:

1. Hoist the existing `topic_kind_lookup(wiki_dir)` call above the `kept` filter — a pure read.
2. Derive the curated name set from it, restricted to `kind` in `{entities, concepts}`. `projects` already route to their own page (#108 FR4); `sources` and `syntheses` are out of scope here.
3. **Exclude folder-context stubs.** `scan_pages` skips `wiki/archive/` (`graph.py:199`) but has **no** underscore skip — it special-cases only `slug in ("README",)` (`graph.py:190`). `wiki/entities/_context.md` therefore already reaches `topic_kind_lookup`, harmless today only because nothing writes `[[_context]]`. The bypass would publish it, which FR5 forbids: skip `_`-prefixed slugs explicitly. A new guard, not a reused one.
4. **Seed** a zero-count `Topic` for any curated page with no topic, keyed on the page title (what wikilinks target). Seed *after* `_cluster_aliases` so clustering sees the input it sees today.
5. **Exempt** curated names from the threshold, matching via the existing `resolve_topic_page` (it already handles slug-vs-title keying) rather than a new comparison.

`build.py:3321` passes `include_curated_pages=True`. **Every other caller keeps the default** — see §3.

**Bypassed node behaviour.** Count 0 or 1 means few or no edges. Already handled: `ui.md:203` specifies Connected topics "Renders `No connected topics.` rather than disappearing"; the viewer side panel already renders a node with no dates (`ui.md:177`). `max_neighbors` prunes each node's *strongest* edges, a no-op at zero edges. The node shows as an isolated vertex, which is truthful.

**Ordering.** No bespoke sort — `topics.py:405` already sorts nodes `(-session_count, id.lower())`, edges at `topics.py:352`/`358`. Seeded zero-count nodes land deterministically last, alphabetically.

**Empty topics get no page (amendment, 2026-09-18 — see functional-spec.md).** A node with **no edges** *and* **no content of its own** would render a page carrying a name, `No connected topics.` and an empty evidence list. `topics_page.prune_empty_isolated_topics(graph, wiki_dir)` drops those nodes, using `_backing_page_markdown` — i.e. `page_content()` — for the content half and the edge list for the connection half, and refreshes `stats["total_topics"] / ["kinds"] / ["top_topics"]` so the listing's headings cannot disagree with the rows under them. Edges need no fixing: a dropped node has none by definition.

It lives in `topics_page.py` rather than `topics.py` because it needs `page_content`, and `topics_page` already imports `topics` (the reverse import would be a cycle). It is **not** folded into `build_topic_graph`: the graph is also the candidate harvest's input (§3), and suppression is a rendering decision about pages, not about what the vocabulary contains.

`build.py` calls it once, immediately after `build_topic_graph` and before `topic_nodes` is read, so the single pruned node list reaches every consumer:

| Consumer | How it sees the suppression |
|---|---|
| `build_topic_pages` | node absent → no `topics/<slug>.html`; the index's sections and counts come from the same list plus the refreshed `stats["kinds"]` |
| `build_search_index(topics=…)` | node absent → no `type: "topic"` entry, so the frozen key set is untouched and the standing invariant ("never index a topic URL this build did not write") holds |
| `build_wiki_corpus_entries(wiki_dir, topics)` | the `site_url` fallback is keyed on `wiki_path` from that same list, so a suppressed page finds no node and keeps `url: null` — the row is listed inert, never pointed at an unwritten page |
| `write_graph_html` / `graph.html` | node absent. Dropped deliberately: the viewer opens `node.site_url` on double-click (`render/graph_viewer.py:294`), so leaving the node in would put an isolated dot on the map whose only gesture is a 404. `use_topic_graph` counts the pruned nodes, which is the count the viewer would actually draw |
| `resolve_project_topic_urls`, `project_connected_topics` | unaffected — both key on edges or on `kind == "projects"`, and a suppressed node has no edges |

### 2.3 Sparse-vault fallback (FR1)

**Three thresholds are easy to confuse — they gate different things, and only one is per-vault configurable:**

| Constant | Value | Gates | Per-vault? |
|---|---|---|---|
| `DEFAULT_MIN_REFS` (`vault_settings.py:39`) | 3 | harvest materialises a candidate stub; `link_integrity` treats an unresolved link as a defect | **yes**, via `llmwiki.json` |
| `min_sessions` (`topics.py:291` default arg) | 2 | a topic becomes a graph node | no — `topics_consolidate` passes its own `_CANDIDATE_MIN_SESSIONS = 2` |
| `_TOPIC_GRAPH_MIN_NODES` (`build.py:3318`) | 5 | whether the topic graph renders at all | no — local constant |

This change touches only the second and third. `min_refs` is untouched; a reader asking "why 5 when promotion needs 3?" is comparing two unrelated gates, and `ui.md` should say so (§2.7).

`build.py:3318` sets `_TOPIC_GRAPH_MIN_NODES = 5`; below it, `build` writes **no topic pages at all** (`build.py:3441-3453`, documented at `ui.md:191`). A vault with three curated entities and no derived topics would still fail FR1. One `if` makes both decisions; decouple:

- **`graph.html`** keeps today's rule — a 2-node graph "looks broken in the viewer" (`build.py:3437`).
- **Topic pages** are written whenever the graph carries any curated-backed node.

`tests/test_topic_graph_sparse_fallback.py` pins current behaviour and is extended, not replaced.

### 2.4 Navigation entry (FR3)

`nav_bar` (`build.py:885`) renders the desktop `.nav-links` row (`build.py:930-938`) and `#nav-drawer` (`build.py:909-918`) from hardcoded literals, eight entries each. Add a ninth, `Topics` → `topics/index.html`, in both, with new `active` key `"topics"`.

- `"topics"` collides with nothing in the existing set (home, raw, candidates, graph, projects, sessions, analytics, docs).
- All 17 `nav_bar` call sites inherit the link; only the two blocks change.
- `topics_page.py:561` (topics index) currently passes `active="graph"` → change to `"topics"`. `topics_page.py:532` (individual topic pages) also passes `"graph"`; left alone (§5).
- No new JS — drawer wiring in `render/js.py` is container-driven, not per-link.
- **Pre-existing quirks, not fixed here:** `build.py:2331` passes `"recent"`, `build.py:2516`/`2571` pass `"models"` — none are real nav keys, so those pages highlight nothing.
- Crowding: a ninth link tightens the desktop row at 1024–1280px (`.nav-links > a` hidden below 1024px, `render/css.py:130`). Checked visually at smoke.

### 2.5 Topics index grouping (FR4)

The index block (`topics_page.py:546-570`) emits one flat `<ul class="topic-index-list">` of `title · N sources · N links`, reach-ordered, with no kind signal. Replace with three sections — Entities, Concepts, Other topics — each heading carrying its count, curated rows carrying a kind chip, existing reach order preserved *within* each section. **No filter or sort controls** (out of scope): the sessions `.filter-bar` JS (`js.py:1675-1680`) is hardcoded to `#sessions-tbody` and is not reusable, and server-rendered grouping needs no JS and cannot fail in the browser (CONTRIBUTING rule 9).

Reuse rather than duplicate (DRY, per `REVIEW_CHECKLIST.md`):

- `kind_label()` (`topics_page.py:177`) — the same labels the palette badge uses.
- `kind_chip()` / `.topic-kind-chip` (`topics_page.py:190-196`) — already used on topic pages.
- `graph["stats"]["kinds"]` (`topics.py:412-415`) — per-kind counts, already computed and currently unused.

### 2.6 Site search mirrors `wiki_search` match mode (FR7)

**Which algorithm.** `wiki_search` has three modes (`mcp/server.py:660-686`). The site mirrors **`mode=match`** — literal term search — not `mode=extract`. They are unrelated algorithms and an earlier draft of this spec specced the wrong one:

| | `mode=extract` | `mode=match` ← this spec |
|---|---|---|
| Matching | tokenised | **literal case-insensitive substring** |
| Scoring | `score_extract`, length-normalised | **none** |
| Ordering | by score | title/path matches first, then body-only; **each group by `rel_path`** |
| Returns | ranked pages + one snippet | page + **every matching line** |

Consequences, all simplifying: no scorer port, no `log2` normalisation, no phrase-bonus decision, and **no tokenisation** — so the Python-vs-JavaScript `\W` Unicode divergence that would have broken parity does not arise. Substring comparison is `String.prototype.includes` on lowercased text in JS and `in` on `.lower()` in Python; these agree for the same input.

**Corpus — the WIKI group.** Exactly what `wiki_search` scans from the wiki, unchanged in extent: **every `.md` under `wiki/` except `archive/`** (`iter_scan_files`, `search/corpus.py:93-111`; `cold_storage_root` withholds only that root's `archive/`). No underscore filter — MCP scans `_context.md` too, and the site must not diverge. On the demo vault that is 205 files: 162 `sources/`, 24 `candidates/`, 9 `entities/`, 4 `concepts/`, 4 root (`index`, `overview`, `log`, `CRITICAL_FACTS`), 1 `categories/`, 1 `syntheses/`.

Raw sessions are **not** in scope: `wiki_search` only reads them behind `include_raw=true`, and this spec adds no requirement for raw search. Site behaviour for raw transcripts is unchanged.

**Destinations.** A WIKI result renders as MCP renders it — `path — title` plus matching lines. The reader URL resolves in two steps, because `_compute_site_url` (`graph.py:94-140`) returns `None` for `entities` and `concepts` via `_NO_SITE_TYPES` (`graph.py:45`) — true before this feature, stale after it, and not fixable there since the topic graph is built later in the pipeline. So: `_compute_site_url` first, then fall back to the backing topic node's own `site_url` keyed by `wiki_path`. The fallback *adopts* a URL from the graph this build actually writes rather than string-building `topics/<slug>.html`, so a curated page with no topic page (an `_`-prefixed stub) stays `null` instead of pointing at a 404. Where either step yields a page the row is a link (`sources/` → its session or document page; `entities/`, `concepts/` → `topics/<slug>.html`; `projects/` → its project page; `wiki/index.md` → `index.html`). Where it yields `None` — `overview.md`, `log.md`, `candidates/`, `syntheses/`, `categories/` — the row still appears with its path and lines but is **not clickable**. This is how full MCP coverage is kept without offering dead-end navigation, and it removes the earlier proposal to exclude `syntheses/`.

**The SITE group.** Everything the palette indexes that is not a wiki page: editorial `docs/`, raw `documents/`, static pages (Home, Graph, Analytics, …), `projects/`, sessions, slash commands. Same match semantics and same ordering rule, applied to its own entries.

**Presentation.** Two groups, WIKI first, **both always rendered** — a group with no hits shows its heading and a zero-results line rather than disappearing, so the reader can tell "nothing in the wiki" from "search is broken". Text-search output caps are MCP's: `DEFAULT_PAGE_CAP = 200` and `DEFAULT_HIT_CAP = 200` (`search/engine.py:23-24`); a group that hits a cap says so, mirroring MCP's `truncated` flag. Empty Site input is a 10-row browse preview; any explicit text/filter/sort query may return 200 rows, and a capped filter-only/sort-only query reports `Showing 200 of N matching results.`

**Index shape.** Substring matching over page bodies, and returning matching *lines*, both require retained page text client-side. The build therefore reuses `iter_scanned_pages`, including deterministic path order, root-containment checks, the 4 MiB per-file cap and the 50 MiB aggregate cap. Retained files are whole rather than partial reads. `search-index.json._wiki_corpus_status` exposes `budget_exhausted` and `skipped_oversize_files`; the palette warns when either makes the static corpus incomplete. Lines are split in the browser rather than precomputed, keeping the payload plain text.

Wiki page text stays **off the eager path**. `search-index.json` is fetched per page view; chunks load once, on first `⌘K` (`loadIndex`, `js.py:923-958`). The build emits the wiki corpus as its own lazy payload — same `.json` + `.js` sidecar treatment as every other payload (#20) — referenced by a new optional manifest key. A site built before this change carries no such key, and the loader must tolerate its absence exactly as it already tolerates the old flat-array format, degrading to a WIKI group that reports zero results with the on-page error already wired through `__llmwikiReportError` (`js.py:943`/`958`), never a silent empty list (CONTRIBUTING rule 9).

**Structured filters.** The existing `type:`/`project:`/`model:`/`date:`/`tags:`/`sort:` query syntax (`js.py:994-1021`) applies to the SITE group only; `wiki_search` match mode has no equivalent beyond `kind`, so applying them to the WIKI group would diverge. `kind:` maps onto MCP's own `kind` filter (frontmatter `type`) and is the one filter both groups honour.

**Measured size impact.** On the committed demo vault the wiki corpus is ~457 KB of text across the pages listed above; on a corpus of ~900 wiki pages it is ~2.3 MB, doubling on disk via the `.js` sidecar. Eager per-page-view cost stays flat because the payload is lazy; whole-site growth is ~4%, since a built site is dominated by rendered session HTML rather than by the index (see #269).

### 2.7 Documentation (CONTRIBUTING rule 6)

- `ui.md:187` asserts "Topics are therefore *not* wiki pages: a topic exists because sessions cited the name". A topic can now also exist *because a curated page describes it* — a documented contract that must be rewritten.
- `ui.md:191` records the curated exemption and the decoupled topic-page rule, and disambiguates the three thresholds above — today it names two of them without distinguishing either from `min_refs`.
- `ui.md:189` describes the new grouping.
- `ui.md:310-313` (search index) records wiki page text in entry bodies and the shared scorer.
- `ui.md:13` nav table gains the Topics row. **Pre-existing drift noted, not fixed:** it also lists **Models** (#7) and **Prototypes** (#9), which `nav_bar` does not render — worth its own issue.
- `docs/reference/mcp.md` states that the site's WIKI result group mirrors `wiki_search` `mode=match` over the same wiki corpus, and that `mode=extract` remains assistant-only.
- `ui.md:296-313` (palette + search index) documents the two result groups, the always-visible zero-results group, match semantics replacing fuzzy scoring for wiki results, non-clickable rows for pages with no reader page, and the 200-page / 200-hit caps.
- `CHANGELOG.md` under `## [Unreleased]` with a release-note bullet.

---

## 3. Impact and Risk Analysis

### System Dependencies

**`llmwiki/topics_consolidate.py:58` is a second caller of `build_topic_graph`**, building the candidate list fed to the LLM consolidator (`build_candidates`). The largest risk here: if the bypass applied there, **already-promoted entities and concepts would re-enter the candidate stream**, and the consolidator would re-decide settled names — a synth-path regression caused by a site feature, close kin to #146. Mitigated by the default-off parameter plus a regression test.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Bypass leaks into candidate harvest (above) | Opt-in parameter, default off; `build_candidates` regression test |
| **Palette behaviour change** — match semantics replace fuzzy scoring, so multi-word queries that are not literal substrings stop returning wiki hits | Accepted and intended: it is what mirroring MCP means. The functional spec records it in Out-of-Scope; e2e covers the empty-group presentation |
| Two groups double the result-rendering paths | One renderer parameterised by group; the zero-results line is the same component. Covered by e2e for both the populated and empty case |
| Substring semantics diverge on case folding for non-ASCII | Both sides lowercase before comparing; parity test includes a Cyrillic term. No tokenisation is involved, which removes the larger `\W` divergence risk |
| WIKI group silently empty when its lazy payload fails | Optional manifest key; absence or load failure yields a zero-results WIKI group **plus** the on-page error report, never a silent empty list |
| `_context.md` stubs published — `scan_pages` has no underscore skip | Explicit `_`-prefix guard; FR5 test |
| Archived pages become reachable — a `CLAUDE.md` hard rule | Two independent guards already hold: `is_archived_path` inside `scan_pages` (`graph.py:199`, the single pinned rule per `tests/test_archive_cold_storage.py`) and `TOPIC_KIND_FOLDERS` excluding `archive`. FR5 test asserts it from this call site, per that file's one-rule-every-reader precedent |
| Text payload missing / stale on an old site | Manifest key is optional; loader degrades to name-only matching and reports on-page. Test covers a site built without the key |
| Text merge creates duplicate rows instead of enriching | Merge is by `id` onto existing meta entries, never `push`. Test asserts entry count is unchanged by the payload |
| First `⌘K` parses ~10× more chunk data | `tests/perf-budgets.json` budgets are per-page *timings*, so the +9 KB eager index is negligible; palette-open time measured in e2e. Chunks already load in parallel and are cached after first load |
| `file://` users get no gzip | Accepted; the eager path grew by 9 KB, and chunk load is deferred to an explicit search |
| Non-deterministic ordering — the #150 failure class | Existing sorts at `topics.py:352/358/405`; assert byte-identical `search-index.json` across two builds |
| Topic-entry key set drifts | `test_search_index_topic_entries_carry_only_the_frozen_keys` guards it; only `body` content changes |
| Topic-page URL set grows, changing `sitemap.xml` / `llms.txt` | Expected; exports derive from the same node list |

### Explicitly unchanged

`llmwiki/mcp/server.py` and `llmwiki/search/*` are not modified — the site adopts their formula, not the reverse. FR6 is proven by measurement, not by that assertion (§4).

---

## 4. Testing Strategy

Gates: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`.

New unit tests follow the existing local-helper pattern (`_session` / `_make_wiki`, `tests/test_topics.py:35-59`) — `tmp_path`-based, no shared conftest — and the richer `_scaffold_vault` / `_write_wiki_page` variant in `tests/test_108_acceptance.py` for whole-build cases.

**Unit — `llmwiki/topics.py`** (extend `tests/test_topics.py`, which has `test_min_sessions_threshold_drops_one_offs:102`)
- Curated entity with **zero** inbound wikilinks yields a node under the flag, none with the default.
- Curated concept with **one** inbound wikilink yields a node under the flag.
- A derived name with one mention and **no** curated page yields **no** node even under the flag — the noise guard FR1's scoping requires.
- A bypassed node carries correct `kind`, `wiki_path`, `site_url`, and zero edges.
- `wiki/archive/` pages and `_`-prefixed stubs never yield a node (FR5).
- Node and edge ordering identical across two runs (#150).

**Regression — synth path**
- `topics_consolidate.build_candidates` output unchanged for a fixture vault holding a below-threshold curated page.

**Integration — `build`**
- Demo vault yields a page and a `⌘K` entry for all 13 curated entities and concepts, including `Python` (FR1, FR2).
- Curated entries carry `kind` `"Entity"`/`"Concept"`; derived topics `"Unclassified topic"` (FR2). Extends `tests/test_topic_search_index.py`.
- A vault below `_TOPIC_GRAPH_MIN_NODES` with a curated page still gets topic pages while `graph.html` falls back — extends `tests/test_topic_graph_sparse_fallback.py`.
- `nav_bar` emits Topics in row and drawer, active on `topics/index.html` (FR3). Extends `tests/test_mobile_hamburger_nav.py`.
- `topics/index.html` renders three counted sections, curated rows chipped, derived rows not (FR4).
- Wiki page text reaches the right carrier entry; `syntheses/` and `archive/` pages reach none (FR7).
- The eager `search-index.json` does **not** grow by page text — entity/concept/project bodies stay short and the text rides in the lazy payload (§2.6).
- Loading the text payload enriches existing entries and leaves the entry count unchanged; a site built without the payload still searches by name and reports the gap on the page.

**Parity — match mode (FR7).** The repo has a real Playwright suite (`tests/e2e/test_search_palette.py`, `test_command_palette.py`, `test_search_index_validation.py`) and `node` is available, so parity is asserted against the original rather than eyeballed. For a fixed set of terms, drive the built demo site and assert the WIKI group's page list and order equal `llmwiki.search.engine.search_match` over the same corpus — covering a title/path match, a body-only match, a term matching both (ordering rule), a multi-word term that must return nothing, a Cyrillic term (case folding), and a term that trips the 200-page cap. Python-side unit tests assert the build emits the same corpus MCP scans: every `.md` under `wiki/` except `archive/`, `_context.md` included.

**Presentation (FR7).** E2e asserts both groups render for a query matching only one of them, that the empty group shows a zero-results line rather than vanishing, and that a result with no site URL is listed but not a link.

**FR6 — assistant-search equivalence.** `tests/test_search_acceptance.py` already gates known-item ranking over the committed demo vault against `tests/fixtures/demo_search_baseline.json` (MRR and rank-1 share, via `llmwiki.search`). It must pass **with that fixture unmodified**. Touching the baseline signals the work stopped being site-only, so the PR must not.

---

## 5. Decisions Taken

All settled with the product owner during specification; recorded so a reviewer does not reopen them.

1. **Topic pages stay canonical.** No `site/entities/` or `site/concepts/` hierarchy — a curated page's existing topic page is its single page.
2. **Topic pages decouple from the sparse-graph fallback** (§2.3). A vault under `_TOPIC_GRAPH_MIN_NODES` still gets topic pages when curated-backed nodes exist; `graph.html` keeps falling back to the page graph. Required by FR1, and it changes behaviour for small and new vaults.
3. **Nav active key changes on the index only** (§2.4). `topics/index.html` highlights **Topics**; individual topic pages keep highlighting **Graph** as they do today.
4. **Site search mirrors `mode=match`, not `mode=extract`** (§2.6) — literal substring, MCP's ordering, MCP's caps.
5. **The WIKI group keeps MCP's full wiki coverage.** Including `candidates/`, `syntheses/`, `categories/` and root files. Pages with no reader page are listed but not clickable, which supersedes an earlier proposal to exclude `syntheses/`.
6. **Raw session search is untouched.** `wiki_search` reads raw only behind `include_raw`, and no requirement here covers it.
7. **Grouped topics index, no controls** (§2.5). Filtering and sorting are separate work.
8. **An empty isolated topic gets no page** (§2.2, amendment 2026-09-18). Suppression is a conjunction — zero edges *and* no content of its own — computed once over the node list so every consumer, including the graph viewer, agrees. The backing wiki page stays in the wiki search corpus with `url: null`.

## 6. Assumptions Flagged

- **Non-clickable rows** are the chosen way to keep MCP coverage without dead-end navigation (§2.6). If a reviewer would rather every result be clickable, the alternative is rendering the missing page types — a new renderer this spec does not carry.
- **Structured filters stay SITE-only** except `kind:` (§2.6), because match mode has no equivalent and applying them to the WIKI group would diverge from MCP.
