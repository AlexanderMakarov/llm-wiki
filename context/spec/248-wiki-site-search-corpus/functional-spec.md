# Functional Specification: Curated knowledge reaches the browsing reader

- **Roadmap Item:** Phase 3 — Visual knowledge depth: entity and concept content reaches readers ([GitHub Issue #248](https://github.com/AlexanderMakarov/llm-wiki/issues/248))
- **Status:** Approved (amended 2026-09-17 — FR7 rewritten for `wiki_search` match-mode parity and two always-visible result groups)
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

**How we measure success.** On the demo wiki, all 13 curated entities and concepts have a page a reader can open and are findable by name in the site's quick search — against 12 of 13 today on both counts, with "Python" missing from each. A reader can get from the site's navigation to a list of curated knowledge in one click. And for a set of sample searches, the wiki pages the site returns — and the order they come back in — match what an assistant returns for the same words.

---

## 2. Functional Requirements (The "What")

- **As a person who curates the wiki, I want every entity and concept I keep to have a page on the site**, so that reviewing and correcting a page is work I can actually see the result of.
  - **Acceptance Criteria:**
    - [ ] Given the wiki contains a curated entity page that no other page mentions by name, when the site is generated, then that entity still has its own page a reader can open.
    - [ ] Given the wiki contains a curated concept page mentioned by only one other page, when the site is generated, then that concept still has its own page a reader can open.
    - [ ] Given the demo wiki's 9 entities and 4 concepts, when the site is generated, then all 13 have a page — including "Python", which has none today.
    - [ ] Given a curated page that records no facts of its own beyond its title, when its page is generated, then the page still opens and shows what kind of thing it is and when it was last reviewed, rather than failing to exist.

- **As a reader, I want the site's quick search to find curated entities and concepts by name and tell me what kind of thing each one is**, so that I can tell a reviewed piece of knowledge from an automatically spotted keyword.
  - **Acceptance Criteria:**
    - [ ] Given the site is open, when I type the name of any curated entity into the quick search, then that entity appears in the results.
    - [ ] Given the site is open, when I type the name of any curated concept into the quick search, then that concept appears in the results.
    - [ ] Given a search result for a curated entity, when I look at it, then it is labelled as an entity, distinctly from results that are automatically derived topics, documents, sessions or projects.
    - [ ] Given a search result for a curated concept, when I look at it, then it is labelled as a concept.
    - [ ] Given a result for a curated entity or concept, when I select it, then I land on that entity's or concept's own page.
    - [ ] Given the demo wiki, when the site is generated, then the quick search offers a correctly labelled curated result for each of the 13 entities and concepts — against 12 today, the 13th ("Python") being absent entirely.

- **As a reader, I want the site's navigation to lead me into the curated knowledge**, so that I can browse what is known without having to guess an address or already know what I am looking for. The listing itself already exists and is already generated on every build — it simply has nothing pointing at it, so no reader arrives there by navigating.
  - **Acceptance Criteria:**
    - [ ] Given any page of the site on a desktop-width screen, when I look at the navigation bar, then it carries an entry labelled **Topics**, which today it does not.
    - [ ] Given any page of the site on a narrow screen, when I open the menu, then the same **Topics** entry is present there too.
    - [ ] Given I am on the knowledge listing, when I look at the navigation, then the **Topics** entry is shown as the current one.
    - [ ] Given I select that navigation entry, when the listing opens, then I can reach any curated entity or concept from it.

- **As a reader browsing the knowledge listing, I want curated entities and concepts marked apart from automatically derived topics**, so that I can tell which knowledge a person has reviewed.
  - **Acceptance Criteria:**
    - [ ] Given the knowledge listing, when I look at it, then curated entities, curated concepts, and automatically derived topics appear in three separate sections, in that order.
    - [ ] Given a section heading on that listing, when I read it, then it states how many items that section holds.
    - [ ] Given a row in the entities or concepts section, when I look at it, then it carries a label naming its kind.
    - [ ] Given a row in the derived-topics section, when I look at it, then it carries no such label.
    - [ ] Given any section of the listing, when I read down it, then the most widely referenced items come first, as they do today.

- **As a wiki owner, I want dismissed and internal pages to stay out of the site**, so that publishing more of the wiki does not publish things I chose to discard.
  - **Acceptance Criteria:**
    - [ ] Given the wiki holds pages a reviewer previously dismissed into cold storage, when the site is generated, then none of them gets a page and none is findable in the quick search.
    - [ ] Given a folder description note that exists only to help assistants navigate the wiki, when the site is generated, then it does not appear as a knowledge item in the listing or the quick search.

- **As an assistant reading the wiki, I want nothing about my access to change**, so that this work carries no risk to existing question answering.
  - **Acceptance Criteria:**
    - [ ] Given an assistant asks the wiki a question, when it does so before and after this change, then it gets the same pages back in the same order.

- **As a reader, I want the site's search to find wiki knowledge exactly as my assistant does, shown separately from ordinary site pages**, so that the site and my assistant never answer the same question differently, and so that I can tell curated knowledge from site navigation at a glance.
  - **Acceptance Criteria:**
    - [ ] Given I search on the site, when results appear, then they are presented in two groups — one for wiki knowledge, one for the rest of the site — with the wiki group first.
    - [ ] Given one of those groups has no match for what I typed, when results appear, then that group is still shown and states that it has no results, rather than disappearing.
    - [ ] Given a word that appears inside a wiki page but not in its title, when I search for it, then that page appears in the wiki group.
    - [ ] Given I search for the same word on the site and through an assistant, when I compare which wiki pages come back and the order they are in, then they agree.
    - [ ] Given results in either group, when I read down them, then pages whose name matches what I typed come before pages that match only in their text.
    - [ ] Given a result whose page the site can open, when I select it, then I land on that page; given a result the site has no page for, then it is still listed with where it lives, but is not offered as something to click.
    - [ ] Given I type several words that do not appear together anywhere, when results appear, then the wiki group reports no results — matching what an assistant would return for the same words.
    - [ ] Given I open the site as plain files rather than through a web server, when I search, then search still works.
    - [ ] Given the search data cannot be loaded, when I search, then the page tells me so rather than silently returning nothing.

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
