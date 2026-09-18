# Functional Specification: Curated knowledge reaches the browsing reader

- **Roadmap Item:** Phase 3 — Visual knowledge depth: entity and concept content reaches readers ([GitHub Issue #248](https://github.com/AlexanderMakarov/llm-wiki/issues/248))
- **Status:** Completed (verified 2026-09-18 — see Verification Notes)
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

The product promises two audiences the same knowledge base. An assistant asking the wiki a question reads the curated layer — the entity and concept pages a person reviews, corrects and keeps — and the per-session summaries. A person browsing the generated site gets neither reliably.

Three problems, measured on the shipped demo wiki (9 entities, 4 concepts, 162 per-session summaries):

1. **A curated page can disappear entirely.** Whether a curated page gets a place on the site depends on how many *other* pages happen to mention it by name — not on whether the page exists. One of the 13 curated pages ("Python") is missing from the site altogether and cannot be found by the site's quick search, though it is real, reviewed, and names three sources of its own. Someone who reviews a candidate and promotes it can do work that never shows up anywhere they can see.
2. **There is no way in from the navigation.** A listing of knowledge topics is already produced on every build, but nothing in the site's navigation bar or mobile menu points at it — there is no **Topics** tab to click. Across the demo site's 355 pages, only two link to that listing. In practice a reader reaches a curated page only by already knowing its address, or by chance through the graph view.
3. **The two searches look at different things and behave differently.** The site's quick search finds a page by its name, but not by the words written inside it, and none of the 162 per-session summaries are searchable at all. The assistant's search reads every page in the wiki and returns them by a rule of its own. The same word typed in both places therefore produces different answers — the split that issue #248 names.

This contradicts the product's stated journey — that people periodically review what the assistants consolidated and then "browse the visual overview and drill into pages" — and its success metric that a person can understand the knowledge landscape in a few seconds and then explore in depth.

**Desired outcome.** Every curated entity and concept a person keeps is reachable on the site, the navigation offers a way to browse the whole set, and searching the site returns the same knowledge in the same order as asking an assistant.

**How we measure success.** On the demo wiki, 12 of the 13 curated entities and concepts have a page a reader can open and are findable by name in the site's quick search — every one that records something of its own or is co-cited with another topic. The thirteenth, "Python", records nothing and is co-cited with nothing, so it gets no page by the empty-page rule below (it is still searchable in the wiki result group, listed without a link). Today's count is also 12 of 13, but a *different* 12: "Python" is missing because nothing links to it, while pages such as "Obsidian" — no facts of their own, 21 connected topics — are absent from the site for the same reach-based reason and return. A reader can get from the site's navigation to a list of curated knowledge in one click. And for a set of sample searches, the wiki pages the site returns — and the order they come back in — match what an assistant returns for the same words.

---

## 2. Functional Requirements (The "What")

- **As a person who curates the wiki, I want every entity and concept I keep to have a page on the site**, so that reviewing and correcting a page is work I can actually see the result of.
  - **Acceptance Criteria:**
    - [x] Given the wiki contains a curated entity page that no other page mentions by name, when the site is generated, then that entity still has its own page a reader can open — provided the page records something of its own, or is co-cited with another topic.
    - [x] Given the wiki contains a curated concept page mentioned by only one other page, when the site is generated, then that concept still has its own page a reader can open.
    - [x] Given the demo wiki's 9 entities and 4 concepts, when the site is generated, then the 12 that record something of their own or are co-cited have a page, and "Python" — which does neither — has none.
    - [x] Given a curated page that records no facts of its own beyond its title but is co-cited with other topics, when its page is generated, then the page still opens and shows what kind of thing it is and when it was last reviewed, rather than failing to exist.
    - [x] Given a curated page that records nothing of its own *and* is co-cited with nothing, when the site is generated, then it gets no page, nothing anywhere on the site links to one, and it stays searchable in the wiki result group as a row with no link.

- **As a reader, I want the site's quick search to find curated entities and concepts by name and tell me what kind of thing each one is**, so that I can tell a reviewed piece of knowledge from an automatically spotted keyword.
  - **Acceptance Criteria:**
    - [x] Given the site is open, when I type the name of any curated entity into the quick search, then that entity appears in the results.
    - [x] Given the site is open, when I type the name of any curated concept into the quick search, then that concept appears in the results.
    - [x] Given a search result for a curated entity, when I look at it, then it is labelled as an entity, distinctly from results that are automatically derived topics, documents, sessions or projects.
    - [x] Given a search result for a curated concept, when I look at it, then it is labelled as a concept.
    - [x] Given a result for a curated entity or concept, when I select it, then I land on that entity's or concept's own page.
    - [x] Given the demo wiki, when the site is generated, then the quick search offers a correctly labelled curated result for each of the 13 entities and concepts — against 12 today, the 13th ("Python") being absent entirely.

- **As a reader, I want the site's navigation to lead me into the curated knowledge**, so that I can browse what is known without having to guess an address or already know what I am looking for. The listing itself already exists and is already generated on every build — it simply has nothing pointing at it, so no reader arrives there by navigating.
  - **Acceptance Criteria:**
    - [x] Given any page of the site on a desktop-width screen, when I look at the navigation bar, then it carries an entry labelled **Topics**, which today it does not.
    - [x] Given any page of the site on a narrow screen, when I open the menu, then the same **Topics** entry is present there too.
    - [x] Given I am on the knowledge listing, when I look at the navigation, then the **Topics** entry is shown as the current one.
    - [x] Given I select that navigation entry, when the listing opens, then I can reach any curated entity or concept from it.

- **As a reader browsing the knowledge listing, I want curated entities and concepts marked apart from automatically derived topics**, so that I can tell which knowledge a person has reviewed.
  - **Acceptance Criteria:**
    - [x] Given the knowledge listing, when I look at it, then curated entities, curated concepts, and automatically derived topics appear in three separate sections, in that order.
    - [x] Given a section heading on that listing, when I read it, then it states how many items that section holds.
    - [x] Given a row in the entities or concepts section, when I look at it, then it carries a label naming its kind.
    - [x] Given a row in the derived-topics section, when I look at it, then it carries no such label.
    - [x] Given any section of the listing, when I read down it, then the most widely referenced items come first, as they do today.

- **As a wiki owner, I want dismissed and internal pages to stay out of the site**, so that publishing more of the wiki does not publish things I chose to discard.
  - **Acceptance Criteria:**
    - [x] Given the wiki holds pages a reviewer previously dismissed into cold storage, when the site is generated, then none of them gets a page and none is findable in the quick search.
    - [x] Given a folder description note that exists only to help assistants navigate the wiki, when the site is generated, then it does not appear as a knowledge item in the listing or the quick search.

- **As an assistant reading the wiki, I want nothing about my access to change**, so that this work carries no risk to existing question answering.
  - **Acceptance Criteria:**
    - [x] Given an assistant asks the wiki a question, when it does so before and after this change, then it gets the same pages back in the same order.

- **As a reader, I want the site's search to find wiki knowledge exactly as my assistant does, shown separately from ordinary site pages**, so that the site and my assistant never answer the same question differently, and so that I can tell curated knowledge from site navigation at a glance.
  - **Acceptance Criteria:**
    - [x] Given I search on the site, when results appear, then they are presented in two groups — one for wiki knowledge, one for the rest of the site — with the wiki group first.
    - [x] Given one of those groups has no match for what I typed, when results appear, then that group is still shown and states that it has no results, rather than disappearing.
    - [x] Given a word that appears inside a wiki page but not in its title, when I search for it, then that page appears in the wiki group.
    - [x] Given I search for the same word on the site and through an assistant, when I compare which wiki pages come back and the order they are in, then they agree.
    - [x] Given results in either group, when I read down them, then pages whose name matches what I typed come before pages that match only in their text.
    - [x] Given a result whose page the site can open, when I select it, then I land on that page; given a result the site has no page for, then it is still listed with where it lives, but is not offered as something to click.
    - [x] Given I type several words that do not appear together anywhere, when results appear, then the wiki group reports no results — matching what an assistant would return for the same words.
    - [x] Given I open the site as plain files rather than through a web server, when I search, then search still works.
    - [x] Given the search data cannot be loaded, when I search, then the page tells me so rather than silently returning nothing.

---

## 3. Scope and Boundaries

### In-Scope

- Every curated entity and concept in the wiki gets a page on the generated site, regardless of how often other pages mention it.
- Curated entities and concepts become findable in the site's quick search, labelled by what kind of thing they are, leading to their own page.
- The site's navigation — both the bar and the narrow-screen menu — gains an entry leading to the existing knowledge listing.
- That listing groups curated entities, curated concepts, and derived topics into three sections with counts, marking the curated ones by kind.
- The site's quick search covers the text of every wiki page an assistant can search, and finds and orders them exactly as the assistant does.
- Search results are presented in two groups — wiki knowledge, then the rest of the site — and both groups always appear, including when one has nothing to show.
- Dismissed pages in cold storage and internal folder-description notes stay out of both the site and its quick search.

### Out-of-Scope

- **A separate page hierarchy for entities and concepts.** Reviewed and rejected during specification: a curated entity's existing knowledge page stays the single page for it, rather than gaining a second, competing one.
- **Publishing the per-session summary pages** as their own pages. Their text becomes searchable, but a result for one opens the session it summarises, which the site already renders.
- **Changing how raw session transcripts are searched.** This work does not alter what the site does with raw transcripts; only wiki knowledge gains assistant-matching behaviour.
- **A forgiving multi-word search over wiki pages.** Matching what an assistant returns means matching it exactly, including returning nothing when the words the reader typed do not appear together on any page.
- **Filtering and sorting controls on the knowledge listing.** The three grouped sections keep today's ordering; controls are separate work.
- **Changing what an assistant searches.** The assistant-facing search is untouched — this work makes the site match it, not the other way round. Its answer quality measurement (#197) and running cost (#244) are also untouched.
- **Improving what curated pages say.** Several curated pages record no facts of their own; giving them a written description is separate work (#137).
- All other roadmap items, addressed in their own specifications — notably one project, one page (#126); candidate review correctness (#146, #139, #148, #149); operator privacy and test isolation (#141, #142); product-facing documentation (#109, #112); the guided health check (#110); hover-to-preview wikilinks, a timeline view and session activity sparklines; a ranking projects index (#129); flipping a concept and an entity (#134); updating an ingested document in place (#151); and Cursor session parsing (#2).

---

## Amendment — the empty-page rule (2026-09-18, post-verification)

Approved by the product owner after reviewing the built demo site. Three of the 37 topic pages the verified build wrote — `topics/python.html`, `topics/dotfiles.html`, `topics/recipe-box.html` — carried a title, `No connected topics.` and an empty evidence list. They help neither a human nor an agent, so the site now writes no page for a topic that has **zero connected topics** *and* **no content of its own** (nothing left of its backing page once the title, `## Connections`, `## Sessions` and `## Sources` are dropped; a topic with no backing page has no content of its own either). Both conditions must hold, and if either is false the page is written as before.

Why the conjunction, measured on the demo vault rather than assumed:

- **Content alone would delete `Obsidian`.** 7 of the 13 curated pages record no facts of their own, `Obsidian` among them — yet it names 29 sources and is co-cited with 21 topics. Its page is one of the most useful on the site.
- **Connections alone would delete a well-written page.** A page someone reviewed and filled in is knowledge worth reading whether or not other sessions happen to mention it in the same breath.
- Only the conjunction isolates the three dead pages: they are the only 3 of 37 with no connected topics, and none of them records anything.

Consequences, all consistent with FR5's "publishing more of the wiki does not publish things I chose to discard": a suppressed topic gets no page, no quick-search entry, no row or count on the knowledge listing, and no node in the graph view. Its wiki page is **not** removed from the wiki search corpus — an assistant still reads it, and FR7 requires the site and the assistant to agree on what the wiki contains — so it is listed in the wiki result group with its path and matching lines and no link, the same treatment FR7 already specifies for a page the site has no page for. Nothing in `wiki/` changes; this is a rendering rule.

## Verification Notes (2026-09-18)

All criteria verified. Evidence:

- **Automated:** full suite 5400 tests, 0 failures, 48 skipped; `ruff` clean. Whole-feature acceptance in `tests/test_248_acceptance.py` (9 tests, RED-validated against a detached worktree at `179d00c`). Parity in `tests/test_248_palette_match.py` (22 node-driven tests asserting equality with `llmwiki.search.engine.search_match` over the real 205-page demo corpus).
- **FR6** is proven by `tests/test_search_acceptance.py` passing with `tests/fixtures/demo_search_baseline.json` unmodified; `llmwiki/mcp/server.py` and `llmwiki/search/**` are untouched in `git diff 179d00c..HEAD`.
- **Rendered verification** against a served build of a private copy of `demo/`: nav carries 9 entries with Topics active only on the listing; listing shows Entities (9) / Concepts (4) / Other topics (23) with chips 9/9, 4/4, 0/23; palette returns Wiki 34 / Site 0 for a wiki-only term, Wiki 0 / Site 2 for a site-only term, and both-zero with messages for a term matching neither; `wiki/overview.md` renders inert (0 anchors, no `data-i`, `aria-disabled="true"`); two real ArrowDown presses advanced to index 2 at DOM position 4, stepping over a heading and the inert row. Screenshots under the gitignored `tests/e2e/screenshots/` (`248-topics-index-grouped.png`, `248-palette-two-groups-inert-row.png`, `248-nav-1024-no-crowding.png`).
- **Nav crowding** (a risk flagged in technical-considerations §2.4, not an acceptance criterion) is resolved: at 1024px — the tightest width where the row renders — all 9 links show with zero overflow at nav, nav-inner and document level, and the last link ends at 784px of 1024.

Two limitations, stated rather than papered over:

1. **`tests/e2e/` did not execute locally.** `pytest-bdd` is absent and PEP 668 refuses installation on the system Python; a global install was correctly declined. The 5 new palette e2e tests are written but unrun here. CI executes them via `.github/workflows/e2e.yml`, whose path filter now includes `llmwiki/render/**`. The parity and presentation properties they cover are separately asserted by the node-driven suite, which does run.
2. **The `file://` criterion is verified at the mechanism level, not by opening the site from disk.** `test_payload_ships_a_js_sidecar` asserts the `.js` sidecar exists, has the expected shape, and carries a payload identical to the JSON — the same properties `tests/test_file_protocol_search.py` uses to certify the index and chunks for `file://`. The MCP browser blocks the `file:` scheme, so the end-to-end open-from-disk path is left to operator smoke confirmation.

