# Tasks: Topic pages show what the wiki knows about a topic (#108)

- **Functional Spec:** [`functional-spec.md`](functional-spec.md)
- **Technical Spec:** [`technical-considerations.md`](technical-considerations.md)

Every slice leaves the vault buildable and the site browsable. Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` before considering any slice done.

**Vault rule for every task:** mutating `llmwiki` commands target the worktree's throwaway vault only — `python3 -m llmwiki build --vault "$PWD/.worktree-vault"` from the worktree root. Never write `raw/`, `wiki/`, or `site/` under the operator's live vault. Always invoke `python3 -m llmwiki`, never PATH `llmwiki`.

---

- [x] **Slice 1: One wikilink parser instead of four**

  > Prerequisite for Slice 4's citation links. Behaviour-preserving: nothing user-visible changes, and the full suite is the regression net. Ordered first so equivalence is pinned before any consumer moves.
  - [x] Write `llmwiki/wikilinks.py` — a leaf module exporting `WIKILINK_RE` (the byte-identical pattern the three agreeing declarations already use) and `wikilink_targets(text)` returning a set of targets with anchors stripped and whitespace trimmed. Both carry docstrings. Import nothing from `llmwiki` so no cycle is possible. **[Agent: general-purpose]**
  - [x] Write equivalence tests **before** migrating any consumer: a shared case table over `[[a]]`, `[[a|b]]`, `[[a#b]]`, `[[a#b|c]]`, `[[a|b#c]]`, `[[#x]]`, and a line holding several links. Assert `wikilink_targets()` output for each, and assert the new pattern plus stripping agrees with `graphify_bridge`'s soon-to-be-retired local variant on every ordinary form — pinning the `[[#x]]` divergence explicitly rather than leaving it implicit. **[Agent: general-purpose]**
  - [x] Delete the four declarations (`llmwiki/graph.py:30`, `llmwiki/lint/__init__.py:36`, `llmwiki/backlinks.py:101`, the function-local one at `llmwiki/graphify_bridge.py:77`) and repoint every importer at `llmwiki.wikilinks` — `synth/pipeline.py:40`, `candidates_harvest.py:21`, `references.py:35`, `lint/rules/orphan_detection.py:8`, `lint/rules/link_integrity.py:7`. Update the importers rather than leaving `graph`/`lint` re-exporting, per CONTRIBUTING. Fix the docstring at `references.py:22` that names `llmwiki.lint.WIKILINK_RE`. **[Agent: general-purpose]**
  - [x] Replace the seven hand-rolled `.split("#")[0].strip()` sites with `wikilink_targets()` where they iterate link targets: `topics.py:140`, `topics.py:258`, `candidates_harvest.py:91`, `backlinks.py:116`, `lint/rules/orphan_detection.py:29`, `lint/rules/link_integrity.py:40`, `references.py:150`. Change only how targets are obtained — not what any consumer does with them. **[Agent: general-purpose]**
  - [x] Add a guardrail test that greps `llmwiki/` for `WIKILINK_RE` declarations and fails if any exists outside `llmwiki/wikilinks.py`, so a fifth copy cannot accumulate. **[Agent: general-purpose]**
  - [x] Verify: full `python3 -m pytest tests/ -q` and `ruff check llmwiki tests scripts` green — the existing suite covers lint rules, synth, backlinks, harvest and the graphify bridge, so a green run is the behaviour-preservation evidence. Build the throwaway vault and confirm `graph.html` still renders. Delete any scratch files produced during the check. **[Agent: general-purpose]**

- [x] **Slice 2: Every topic page says what kind of thing it is**

  > FR1 + FR8. First user-visible increment: a reader can tell a codebase from an idea from an unfiled name.
  - [x] Extend `topic_kind_lookup()` (`llmwiki/topics.py:197`) to map a lowercased slug/title to a record carrying `kind`, `slug`, `path`, `last_updated` and the `site_url` `scan_pages` already computed — instead of discarding all but the folder name. Rename `resolve_topic_kind()` to `resolve_topic_page()`, returning the record or `None`, preserving the canonical-then-aliases precedence. Keep `kind` folder-derived; do not read it from frontmatter (pre-#102 project pages depend on this). **[Agent: general-purpose]**
  - [x] Carry `wiki_slug`, `wiki_path` and `site_url` onto each node in `build_topic_graph()` (`llmwiki/topics.py:262`), omitting them for a topic no page describes. Leave existing `kind` semantics untouched. **[Agent: general-purpose]**
  - [x] Render FR1's identity line in `build_topic_pages()` (`llmwiki/topics_page.py:96`): kind chip, connected-topic count, session count, and the page's short name. Every element is omitted entirely when its field is absent — no labels without values, no placeholder text. **[Agent: general-purpose]**
  - [x] Unit tests: `resolve_topic_page()` matches on canonical spelling, falls back to aliases in sorted order, returns `None` on no match; nodes omit the new keys for an undescribed topic; the identity line renders each element only when present. **[Agent: general-purpose]**
  - [x] Verify: build a fixture vault holding an entity, a concept, a project and a topic no page describes. Assert the first three render a kind chip and the fourth renders none, with no empty heading and no dangling label anywhere on the page. Delete the fixture output afterwards. **[Agent: general-purpose]**

- [x] **Slice 3: Topic pages show when the topic was active and when it was reviewed**

  > FR2 for topics. Two distinct facts, separately labelled, neither invented.
  - [x] Add `last_updated` and `date` to `scan_pages()`'s returned record (`llmwiki/graph.py:147`), sourcing both from `parse_frontmatter()` (`llmwiki/_frontmatter.py`) in place of the ad-hoc title regex at `graph.py:176`. Purely additive. Title-extraction behaviour must not change — a page with no frontmatter still falls back to its slug. **[Agent: general-purpose]**
  - [x] Add `date` to `sessions_meta` (`llmwiki/topics.py:295`), and derive `first_seen` / `last_seen` per node from the earliest and latest session dates. Carry the backing page's `last_updated` onto the node. Absent values stay `None` — never a placeholder string. **[Agent: general-purpose]**
  - [x] Render activity dates and the review date in the identity line, labelled so a reader can tell them apart. Omit each independently when absent. **[Agent: general-purpose]**
  - [x] Unit tests: `scan_pages()` returns both fields when present and `None` when absent; the no-frontmatter title fallback is unchanged; `last_updated` parses identically whether written quoted or bare; first/last-seen derive from the correct sessions and are absent when no session carries a date. **[Agent: general-purpose]**
  - [x] Verify: build a fixture vault mixing pages with dates, pages with only some, and pages with none. Assert each renders only the dates it actually has, and that a page with neither shows no date and no empty label. Delete the fixture output afterwards. **[Agent: general-purpose]**

- [x] **Slice 4: Entity and concept pages' content reaches the reader**

  > FR3 — the payload of the whole change. People and ideas have no site page of their own, so this is the only surface their curated content can reach.
  - [x] Add a content-extraction helper to `llmwiki/topics_page.py`: strip frontmatter, drop the leading `# H1`, drop the `## Connections` and `## Sessions` sections (heading through to the next `##` or end of file), and return what remains — or `None` when nothing is left. Heading-agnostic beyond those two exclusions, so it survives #109 renaming `## Key Facts` and never drops a section a curator added. **[Agent: general-purpose]**
  - [x] Render that content above the connected-topics list, via `md_to_html()` through the module's existing deferred-import block (`topics_page.py:101`, already carrying `# noqa: PLC0415` for the `build ↔ topics_page` cycle). Emit no heading at all when the helper returns `None`. **[Agent: general-purpose]**
  - [x] Resolve `[[wikilinks]]` inside that content using Slice 1's helper: a target matching a topic links to its sibling topic page, a target matching a session links to `../<site_url>`, and anything unresolvable degrades to plain text with the link markup removed. Escape every attribute constructed. **[Agent: general-purpose]**
  - [x] Unit tests: extraction drops frontmatter, H1, Connections and Sessions while keeping intro prose, Key Facts and other sections; returns `None` for a page with nothing left. Link resolution covers all three outcomes. **[Agent: general-purpose]**
  - [x] Verify: build a fixture vault with an entity page carrying Key Facts and citations, a concept page carrying only prose, and an entity page with an empty Key Facts section. Assert content renders above Connected topics, citations become working links, unresolvable ones are plain text, and the empty page emits no heading. Delete the fixture output afterwards. **[Agent: general-purpose]**

- [x] **Slice 5: Clicking a project in the map opens its project page**

  > FR4. The project page already exists and is rich; the map has been sending readers to a thin substitute.
  - [x] Add `resolve_project_topic_urls(graph, built_project_slugs)` to `llmwiki/topics.py`: for each node with `kind == "projects"` whose `wiki_slug` is in the built set, adopt the backing page's already-correct `site_url`; leave the rest on `topics/<slug>.html`. Return the count rewritten. The membership test is the substance — `wiki/projects/` is written by `ensure_project_stubs()` while `site/projects/` comes from session groups, so the two sets can differ. **[Agent: general-purpose]**
  - [x] Call it once from `build.py` with `set(groups)`, after the graph is built and before `write_graph_html()` and `build_topic_pages()`, so the viewer's double-click target and the static page agree. **[Agent: general-purpose]**
  - [x] Unit tests: only project nodes in the built set are rewritten; an unmatched project node keeps its topic URL; the returned count is correct; a non-project node is never touched. **[Agent: general-purpose]**
  - [x] Verify: build a fixture vault with a project that has sessions and a hand-authored `wiki/projects/*.md` that has none. Assert the first resolves to `projects/<slug>.html` in both `graph.html` and the topic page, and the second falls back to an ordinary topic page with no error and no broken link. Delete the fixture output afterwards. **[Agent: general-purpose]**

- [x] **Slice 6: Project pages gain connections and honest dates**

  > FR5 + FR2's project half. This is what makes Slice 5 lossless — without it, forwarding would discard the co-occurrence data only topic pages carry.
  - [x] Move the `build_topic_graph()` block (`build.py:3146-3153`) above the `render_project_page()` loop at `build.py:3083`, carrying `use_topic_graph` / `_TOPIC_GRAPH_MIN_NODES` unchanged. It is pure CPU over the wiki and writes nothing; the existing `try/except` keeps a graph failure from breaking project pages. **[Agent: general-purpose]**
  - [x] Give `render_project_page()` (`build.py:1372`) an optional connected-topics parameter — `list[tuple[str, int]]`, the shape `_neighbors()` already returns — defaulting to empty so existing callers and tests are unaffected. Render the section immediately above `<h2>Main sessions …</h2>` (`build.py:1506`), and emit nothing at all when the list is empty. Do not confuse this with the existing hero topic chips from `get_project_topics()`, which are different data in a different place. **[Agent: general-purpose]**
  - [x] Derive each project's created and updated dates from its oldest and newest session and render them in the project hero, so they stay correct as sessions arrive without anyone editing a stub. **[Agent: general-purpose]**
  - [x] Unit tests: the connected-topics parameter defaults empty and emits no section; project dates derive from the correct sessions; a project whose sessions carry no dates shows none. **[Agent: general-purpose]**
  - [x] Verify: build the throwaway vault and confirm a project page shows Connected topics directly above its session list and created/updated dates in the hero. Then build a vault below `_TOPIC_GRAPH_MIN_NODES` and confirm it completes with no topic pages and no Connected topics section — not an empty one. Delete the fixture output afterwards. **[Agent: general-purpose]**

- [x] **Slice 7: Every kind is a different colour in the map**

  > FR6. Codebases currently share a colour with topics nothing describes — the two least similar things in the map.
  - [x] Add `--g-node-projects` `#db2777`, `--g-node-questions` `#0891b2`, `--g-node-comparisons` `#b45309` and `--g-node-other` `#65a30d` to **both** theme blocks (`llmwiki/graph.py:310` dark, `:328` light), and the matching four entries to the `colors` map (`graph.py:615`). Keep `colors.topic` as the last-resort fallback for unknown strings. **[Agent: general-purpose]**
  - [x] Tests over the generated `graph.html`: all four variables present in both theme blocks; the `colors` map has an entry for every kind in `TOPIC_KIND_FOLDERS` plus `other`; no two kind colours are equal; and no kind colour equals `--g-orphan` or `--g-search-match` in either theme — red stays reserved for those two signal states. **[Agent: general-purpose]**
  - [x] Verify: build the throwaway vault, open `graph.html`, and confirm the legend shows one distinct swatch per kind present with no two alike, in both light and dark themes. Delete any screenshots produced during the check. **[Agent: general-purpose]**

- [x] **Slice 8: The map's side panel says what the page says**

  > FR7 — triage without opening every page.
  - [x] Extend `showTopicPanel()` (`llmwiki/graph.py:908`) with a kind row and a freshness row after the existing session and connection stats, each omitted when the node lacks the field. Pass every interpolated value through the existing `escapeHtml()`. Route any new failure path through `reportGraphError()` (`graph.py:632`) so it surfaces on the page via `window.__llmwikiReportError` rather than only in the console. **[Agent: general-purpose]**
  - [x] Tests over the generated `graph.html`: the panel emits kind and freshness rows, and omits them for a node carrying neither. **[Agent: general-purpose]**
  - [x] Verify: build the throwaway vault, open `graph.html`, select a described topic and an undescribed one, and confirm the panel shows kind and freshness for the first and neither — with no empty rows — for the second. Delete any screenshots produced during the check. **[Agent: general-purpose]**

- [x] **Slice 9: Documentation**

  > FR9. `docs/reference/ui.md` documents every site surface except topic pages.
  - [x] Add a topic-pages section to `docs/reference/ui.md` covering the identity line, the content block, and the project routing; update its Projects and Graph sections for the connections list and the per-kind colours. State which information comes from sessions and which from the topic's own page. **[Agent: general-purpose]**
  - [x] Add a `CHANGELOG.md` entry under `## [Unreleased]` describing the user-visible change and noting that existing vaults need no migration or re-sync. **[Agent: general-purpose]**
  - [x] Verify: link-check the touched docs and confirm no relative link 404s. **[Agent: general-purpose]**

- [x] **Slice 10: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 004-topic-page-kind-and-key-facts` and `@regression` if suitable for long-term regression. Include the backward-compatibility criteria from technical-considerations.md §3: a vault carrying none of the optional frontmatter, a pre-#102 project page (`type: entity` + `entity_type: project` under `wiki/projects/`), quoted vs bare `last_updated`, and a guardrail that topic entries in `site/search-index.json` carry exactly the keys they carry today. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–9 (all implementation tasks) | Assigned to `general-purpose` — `context/product/hired-agents.md` records no Python/CLI or static-site specialist; template-generated agents were declined during `/awos:hire` | Optional: re-run `/awos:hire` if a suitable registry Python agent appears. The `modern-python-development` and `pytest-best-practices` skills are installed and apply regardless |
| Slices 7–8 (viewer verification) | Visual confirmation of colours and the side panel benefits from a browser | Playwright MCP is available in-session; string assertions over the generated `graph.html` are the primary gate, with the browser as confirmation only |
| Slice 10 (QA) | None — `testing-expert` is registered and matches | — |
| `testing-expert` prerequisite | Its own docs expect the testing stack declared in `context/product/architecture.md`, which currently does not name pytest / ruff | Pass the stack explicitly when dispatching, or add it to `architecture.md` in a separate change |
