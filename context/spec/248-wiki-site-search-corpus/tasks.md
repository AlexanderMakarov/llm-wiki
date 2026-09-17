# Tasks: Curated knowledge reaches the browsing reader (#248)

Spec: [`functional-spec.md`](functional-spec.md) · [`technical-considerations.md`](technical-considerations.md) — both Approved.

**Standing constraints for every task.** Work only in the worktree `.claude/worktrees/feat-248-wiki-site-search-corpus` on branch `feat/248-wiki-site-search-corpus`. Vault-mutating commands target `$TMP_VAULT` (`.worktree-vault`) or an explicit `--out` under the scratchpad; never the operator's live vault. Always drive `python3 -m llmwiki` from the worktree, never PATH `llmwiki`. Gates before any slice is called done: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`.

**Do not touch** (FR6 is proven by these staying green and unmodified): `llmwiki/mcp/server.py`, `llmwiki/search/**`, `tests/fixtures/demo_search_baseline.json`. `tests/test_search_acceptance.py` must pass with that fixture untouched.

**Do not change** the topic search-entry key set — `tests/test_108_acceptance.py::test_search_index_topic_entries_carry_only_the_frozen_keys` is a deliberate guardrail.

---

- [x] **Slice 1: A curated entity or concept always gets a topic page**

  > FR1 + FR2. Ends with `Python` — today invisible — having a page and a correctly badged palette entry on the demo vault.
  - [x] Add `include_curated_pages: bool = False` keyword to `build_topic_graph` (`llmwiki/topics.py:287`). Hoist the existing `topic_kind_lookup(wiki_dir)` call (`topics.py:366`) above the `kept` filter. When the flag is on: build the curated set from pages whose kind is `entities` or `concepts`, **explicitly skipping `_`-prefixed slugs** (`scan_pages` has no underscore filter — `graph.py:190` skips only `README`); seed a zero-count `Topic` keyed on page title for any curated page `derive_vocabulary` produced no topic for, seeded *after* `_cluster_aliases` so clustering sees unchanged input; and exempt curated names from the `min_sessions` threshold, matching via the existing `resolve_topic_page`. Leave node/edge sorting alone — `topics.py:352/358/405` already make ordering deterministic. **[Agent: general-purpose]**
  - [x] Pass `include_curated_pages=True` from the site build only (`llmwiki/build.py:3321`). `llmwiki/topics_consolidate.py:58` must keep the default — see the regression task below. **[Agent: general-purpose]**
  - [x] Extend `tests/test_topics.py` (reuse `_session`/`_make_wiki` at `:35-59`, alongside `test_min_sessions_threshold_drops_one_offs:102`): curated entity with **zero** inbound wikilinks yields a node under the flag and none with the default; curated concept with **one** inbound wikilink yields a node under the flag; a derived name with one mention and **no** curated page yields no node even under the flag; a bypassed node carries correct `kind`, `wiki_path`, `site_url` and zero edges; `wiki/archive/` pages and `_`-prefixed stubs never yield a node; node and edge ordering identical across two runs. **[Agent: general-purpose]**
  - [x] Add the synth-path regression: `topics_consolidate.build_candidates` returns identical output for a fixture vault containing a below-threshold curated page. This is the guard against promoted entities re-entering the candidate stream (#146 bug class) — the single largest risk in this change. **[Agent: general-purpose]**
  - [x] Verify: build the committed demo vault to a scratch `--out`, assert `topics/python.html` now exists and that `search-index.json` carries a `kind: "Entity"` entry for Python, then confirm all 13 demo entities and concepts are present. Delete the scratch build directory when done. **[Agent: general-purpose]**

- [x] **Slice 2: Small vaults still get topic pages**

  > FR1 for vaults under the viewer's node threshold, which is most new users.
  - [x] Decouple topic-page writing from graph rendering in `llmwiki/build.py:3318` and `:3441-3453`. `graph.html` keeps today's `_TOPIC_GRAPH_MIN_NODES = 5` page-graph fallback (a 2-node graph "looks broken in the viewer", `build.py:3437`); topic pages are written whenever the graph carries any curated-backed node. **[Agent: general-purpose]**
  - [x] Extend `tests/test_topic_graph_sparse_fallback.py` rather than replacing it: its existing graph-side assertion must still hold, plus a new case where a vault below the threshold with at least one curated page gets topic pages while `graph.html` still falls back. **[Agent: general-purpose]**
  - [x] Verify: build a fixture vault with fewer than five topic nodes and at least one curated page; confirm `topics/*.html` are written and `graph.html` used the page-graph fallback. Remove the fixture build afterwards. **[Agent: general-purpose]**

- [x] **Slice 3: A Topics entry in the navigation**

  > FR3. The topics listing is already generated on every build; nothing points at it.
  - [x] Add a ninth entry `Topics` → `topics/index.html` with `active` key `"topics"` to **both** blocks of `nav_bar` (`llmwiki/build.py:909-918` drawer, `:930-938` desktop row). All 17 call sites inherit it; no other call site changes. Do not touch the pre-existing dead keys `"recent"` (`build.py:2331`) and `"models"` (`:2516`, `:2571`). **[Agent: general-purpose]**
  - [x] Change `llmwiki/topics_page.py:561` from `active="graph"` to `active="topics"` so the listing marks itself current. Leave `topics_page.py:532` (individual topic pages) on `"graph"` — a decision recorded in technical-considerations §5.3. **[Agent: general-purpose]**
  - [x] Extend `tests/test_mobile_hamburger_nav.py` (it pins the drawer markup/CSS/JS contract) to assert the Topics link appears in both the desktop row and the drawer, and that `topics/index.html` renders it active. **[Agent: general-purpose]**
  - [x] Verify: build the demo vault and confirm the Topics link is present in the nav of a page from each directory depth (root, `topics/`, `sessions/<project>/`) so `link_prefix` handling is right at `""`, `"../"` and `"../../"`. Check the desktop row at 1024–1280px for crowding. Delete the build and any screenshots afterwards. **[Agent: general-purpose]**

- [x] **Slice 4: The topics listing separates curated knowledge from derived topics**

  > FR4. Three counted sections; no filter or sort controls (out of scope).
  - [x] Rewrite the index block in `llmwiki/topics_page.py:546-570` to emit three sections — Entities, Concepts, Other topics — each heading carrying its count, curated rows carrying a kind chip, and today's reach ordering preserved *within* each section. Reuse `kind_label()` (`topics_page.py:177`), `kind_chip()` / `.topic-kind-chip` (`:190-196`) and `graph["stats"]["kinds"]` (`topics.py:412-415`) rather than adding parallel machinery. Server-rendered only — no new JS. **[Agent: general-purpose]**
  - [x] Add tests asserting the three sections with correct counts, a kind chip on curated rows, no chip on derived rows, and reach ordering preserved inside each section. Keep `tests/test_108_acceptance.py`'s existing `topics/index.html` assertion passing. **[Agent: general-purpose]**
  - [x] Verify: build the demo vault, open `topics/index.html`, confirm 9 entities / 4 concepts / 23 other topics with chips on the first two groups only. Delete the build afterwards. **[Agent: general-purpose]**

- [x] **Slice 5: The build emits the wiki corpus as a lazy search payload**

  > FR7, build half. Nothing changes in the palette yet; this slice is verified by the payload's shape and by what it does *not* do to the eager index.
  - [x] In `llmwiki/build.py`, emit the wiki corpus as its own payload: **every `.md` under `wiki/` except `archive/`**, matching `iter_scan_files` (`search/corpus.py:93-111`) exactly — `_context.md` **included**, since MCP scans it. Carry full page text (no cap) plus `rel_path`, `title`, and the reader URL from `_compute_site_url` (`graph.py:94-140`), which is `None` for `overview.md`, `log.md`, `candidates/`, `syntheses/` and `categories/`. Write it with the `.json` + `.js` sidecar treatment via `write_js_sidecar` (#20) and reference it from a **new optional manifest key** beside `_chunks`. **[Agent: general-purpose]**
  - [x] Keep it off the eager path: `search-index.json` must not grow by page text. Entity, concept and project meta entries keep their current short bodies, and the topic entry key set stays frozen. **[Agent: general-purpose]**
  - [x] Tests: the emitted corpus equals what MCP scans (assert against `iter_scan_files` over the same fixture, including `_context.md` and excluding `archive/`); the eager `search-index.json` does not grow by page text; `tests/test_108_acceptance.py::test_search_index_topic_entries_carry_only_the_frozen_keys` still passes; and two builds of one vault produce byte-identical payloads (#150 determinism). **[Agent: general-purpose]**
  - [x] Verify: build the demo vault, confirm the payload lists 205 wiki files with the expected per-folder split (162 sources, 24 candidates, 9 entities, 4 concepts, 4 root, 1 categories, 1 syntheses), that `.js` sidecars exist beside every `.json`, and that the eager index is essentially unchanged in size. Delete the build afterwards. **[Agent: general-purpose]**

- [x] **Slice 6: The palette searches the wiki exactly as `wiki_search` match mode does**

  > FR7, viewer half. Two always-visible groups, WIKI first.
  - [x] In `llmwiki/render/js.py`, implement match semantics for the WIKI group, mirroring `mode=match` (`mcp/server.py:689-750`, `search/scoring.py:84`): literal case-insensitive substring (lowercase both sides — no tokenisation, so no `\W` Unicode divergence); ordering is title/path matches first, then body-only matches, **each group sorted by `rel_path`**; matching lines split client-side; caps `DEFAULT_PAGE_CAP = 200` and `DEFAULT_HIT_CAP = 200` (`search/engine.py:23-24`) with a truncation note mirroring MCP's `truncated`. **[Agent: general-purpose]**
  - [x] Render two groups, WIKI first, **both always present** — a group with no hits shows its heading and a zero-results line rather than disappearing, so "nothing in the wiki" is distinguishable from "search is broken". Rows whose reader URL is `None` are listed with their path and lines but are **not clickable**. **[Agent: general-purpose]**
  - [x] Apply the same match semantics and ordering to the SITE group (editorial `docs/`, raw `documents/`, static pages, `projects/`, sessions, slash commands). Keep the structured filters `type:`/`project:`/`model:`/`date:`/`tags:`/`sort:` (`js.py:994-1021`) SITE-only; `kind:` is the one filter both groups honour, mapping onto MCP's frontmatter `type` filter. **[Agent: general-purpose]**
  - [x] Handle a missing or failed payload: the WIKI group reports zero results **and** the existing `__llmwikiReportError` path fires (`js.py:943`/`958`). Never a silent empty list — CONTRIBUTING rule 9. A site built before this change has no manifest key and must still load, exactly as the loader already tolerates the old flat-array format. **[Agent: general-purpose]**
  - [x] Parity tests against the original, using the existing Playwright suite (`tests/e2e/test_search_palette.py`, `test_command_palette.py`) and `node`: for a fixed set of terms, assert the WIKI group's page list and order equal `llmwiki.search.engine.search_match` over the same corpus. Cover a title/path match, a body-only match, a term matching both (the ordering rule), a multi-word term that must return nothing, a Cyrillic term (case folding), and a term that trips the 200-page cap. **[Agent: general-purpose]**
  - [x] Presentation tests: both groups render for a query matching only one of them; the empty group shows its zero-results line rather than vanishing; a result with no reader page is listed but is not a link. **[Agent: general-purpose]**
  - [x] Verify: build the demo vault, drive the palette in a browser, and confirm both groups render for a wiki-only term, a site-only term, and a term matching neither. Delete the build and any screenshots or generated scripts afterwards. **[Agent: general-purpose]**

- [x] **Slice 7: Documentation and changelog**

  > CONTRIBUTING rule 6. Several of these are documented contracts, not prose.
  - [x] `docs/reference/ui.md`: rewrite line 187 — "Topics are therefore *not* wiki pages: a topic exists because sessions cited the name" is now false, since a topic can exist because a curated page describes it. Update line 191 to record the curated exemption, the decoupled topic-page rule, and to disambiguate the three thresholds readers currently conflate: `DEFAULT_MIN_REFS = 3` (harvest + `link_integrity`, the only per-vault configurable one), `min_sessions = 2` (graph node admission), `_TOPIC_GRAPH_MIN_NODES = 5` (whether the graph renders at all). Update line 189 for the grouped listing. Update lines 296-313 for the two result groups, the always-visible zero-results group, match semantics replacing fuzzy scoring for wiki results, non-clickable rows, and the 200/200 caps. The Topics row in the nav table (line 13) was **already added under Slice 3**, forced by the `tests/test_reference_coverage.py` nav-key contract — verify it reads correctly, do not duplicate it. **Do not** fix the pre-existing Models/Prototypes drift in that table, which belongs to its own issue. **[Agent: general-purpose]**
  - [x] `.github/workflows/e2e.yml`: add `llmwiki/render/**` to BOTH the `push` and `pull_request` path filters. The palette lives in `llmwiki/render/js.py`, which is absent from the current list — this PR triggers e2e only incidentally via `llmwiki/build.py`, so a future palette-only change would skip browser tests entirely. Two lines; do not restructure the workflow. **[Agent: general-purpose]**
- [x] `docs/reference/mcp.md`: state that the site's WIKI result group mirrors `wiki_search` `mode=match` over the same wiki corpus, and that `mode=extract` stays assistant-only. **[Agent: general-purpose]**
  - [x] `CHANGELOG.md` under `## [Unreleased]` with a one-line release-note bullet, following the existing entry style (issue number, user-visible behaviour, breaking flags where applicable). **[Agent: general-purpose]**
  - [x] Verify: run the repo's link-check hygiene over the touched docs and confirm no committed `*.md`/`*.py` trips the CI privacy grep (`.github/workflows/ci.yml` holds the enforced list — read it rather than guessing). **[Agent: general-purpose]**

- [x] **Slice 8: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 248-wiki-site-search-corpus` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–7 (all implementation tasks) | Assigned to `general-purpose` — `context/product/hired-agents.md` records Python/CLI coverage as "⚠️ Partial — skills installed; no dedicated agent (user declined template-generated agents)" | The `modern-python-development` and `pytest-best-practices` skills are installed and will carry most of the load. Re-run `/awos:hire` if a suitable registry Python agent appears. |
| Slices 4, 6 (static-site + viewer JS) | `static-html-site` role recorded as "❌ Missing — out of lean hire set" | Hire a static-site/frontend specialist if viewer JS work becomes a recurring bottleneck; `frontend-design` skill is available in-session meanwhile. |
| Slice 8 (QA) | `testing-expert` is registered and used | `hired-agents.md` notes it "expects testing stack declared in `context/product/architecture.md`" — that file does not currently declare pytest/ruff/the Playwright harness. Worth adding so the agent does not have to infer it. |
| Slice 6 (Verify) | Browser automation needed | Playwright is available in-session and `tests/e2e/` already uses it; `node` is present for the parity assertions. No install required. |
