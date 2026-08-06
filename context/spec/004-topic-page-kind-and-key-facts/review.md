# Maintainer review — `feat/108-topic-page-kind-key-facts`

**Verdict: approve with changes.** No blockers. The feature does what `functional-spec.md` says it does, the wikilink consolidation was justified and executed safely, and the whole suite plus `ruff` is green locally. Seven non-blocking findings and seven nits below, one of which (N1) is a user-visible routing gap that contradicts FR4's own "every surface" claim.

Scope reviewed: `git diff origin/main...HEAD` — 8 commits, 36 files, +3701/−122. Verified locally in the worktree:

```
ruff check llmwiki tests scripts   → All checks passed!
python3 -m pytest tests/ -q        → green (no failures, only pre-existing skips)
```

---

## Blockers

**None.** Nothing in this diff breaks users, loses data, ships a security problem, or violates a hard CONTRIBUTING rule outright. See "Checklist coverage" for the sections that were applied and came back clean.

---

## Non-blocking findings

### `llmwiki/build.py`

**N1 — Connected topics on a project page do not honour project routing (contradicts FR4 + `ui.md`).**
`render_connected_topics()` (`llmwiki/build.py:1560-1576`) hardcodes the href:

```python
f'<li><a href="../topics/{html.escape(topic_slug(name), quote=True)}.html">'
```

Every other surface routes a project-kind topic to `projects/<slug>.html` — `resolve_project_topic_urls()` rewrites `node["site_url"]`, and `topics_page._topic_href()` consumes it for topic pages, `topics/index.html`, and `[[wikilink]]` citations. This one list does not. Condition: two projects co-occur in the graph (a `wiki/sources/*.md` summary linking both project names, which the vocabulary happily clusters). Result: on project A's page, project B in the Connected topics list sends the reader to `topics/b.html` — the thin substitute page that FR4 exists to route readers away from. `docs/reference/ui.md:145` describes the project-page list as linking to `../topics/<slug>.html`, so the docs are self-consistent, but the Topic-pages section two screens down claims the rewrite is honoured on "every surface", and a reader clicking a codebase gets the stripped page either way.

This is invisible to the tests: `tests/test_project_page_connections.py:274 test_every_connected_topic_link_resolves_to_a_real_file` asserts the target exists on disk, and `topics/<project>.html` *is* still written for every node — so a routed-away page satisfies the assertion.

*Fix:* thread the resolved URLs into the renderer instead of reconstructing the path. `topics_page._node_urls()` already produces the map, and `_topic_href()` already knows the `topics/` vs `../` rule — promote both to public and call them with a `"../"` prefix, or pass `project_connected_topics()` a `list[tuple[str, int, str]]` carrying each neighbour's resolved URL. Add a case to `test_project_page_connections.py` with two projects sharing a session and assert the link is `../projects/<other>.html`.

**N2 — `build.py` imports a private helper across module boundaries.**
`llmwiki/build.py:116`:

```python
from llmwiki.topics_page import _neighbors, build_topic_pages, kind_chip, kind_label
```

`_neighbors` (`llmwiki/topics_page.py:79`) is named private, and its docstring documents no cross-module contract. Importing it at `build.py` module scope makes it a de-facto public API whose signature is now load-bearing for `project_connected_topics()` and for the docstring at `build.py:1441` that names it. `ruff` does not flag this, so nothing stops it drifting. CONTRIBUTING's "prefer importing helpers from the owning module over high-level facade re-exports" is satisfied; what is not satisfied is that the name says "do not import me".

*Fix:* rename to `neighbors()` in `llmwiki/topics_page.py`, update the three in-module call sites and the `build.py` import and docstring reference. No alias needed — the name is not part of any released contract.

### `llmwiki/render/css.py`

**N3 — Comment states the opposite of the shipped behaviour.**
`llmwiki/render/css.py:828-831`:

```css
/* Topic-page identity line (#108) — the chip naming what kind of thing
   the topic is. Same pill shape as .topic-chip, sized for the hero
   subtitle it sits in. Topics no wiki page describes render no chip. */
```

The last sentence is false and inverts the single most deliberate decision in FR1/FR8: `topics_page.kind_label()` returns `KIND_OTHER_LABEL` ("Unclassified topic") precisely so that the chip is *never* dropped, because "a reader seeing no chip cannot tell whether the topic is unclassified or whether the page simply failed to say" (`functional-spec.md:37`). A future contributor reading this comment while chasing a rendering bug will conclude the always-present chip is the bug. REVIEW_CHECKLIST "docstrings match the code".

*Fix:* replace the last sentence with "A topic no wiki page describes still renders a chip, reading `Unclassified topic` — see `topics_page.KIND_OTHER_LABEL`."

### `llmwiki/topics_page.py`

**N4 — Wikilink resolution runs inside code spans and fenced blocks.**
`_resolve_wikilinks()` (`llmwiki/topics_page.py:329-355`) applies `WIKILINK_RE.sub()` to the entire `md_to_html()` output. `md_to_html` preserves fenced and inline code verbatim (`build.py:_md_to_html_uncached` registers `_EscapeRawHtmlPreprocessor` at priority 22, after `fenced_code`), so a backing page that documents wikilink syntax —

````markdown
Cite the source like this:

```
- Fact ([[some-session-slug]])
```
````

— emits `<code>[[some-session-slug]]</code>`, and `_resolve_wikilinks` rewrites the example inside the code block into a live anchor. The example stops being an example, and if the target resolves to nothing the brackets are stripped from what the curator wrote verbatim. Not a security issue (the label is already markdown-escaped, and the href is `html.escape(..., quote=True)`d), but it silently edits code the page meant to show literally.

*Fix:* split the rendered HTML on `<pre>…</pre>` and `<code>…</code>` and only substitute in the gaps, or state the limitation in `docs/reference/ui.md`'s "Page content" bullet list, which currently promises `[[wikilinks]]` "resolve" without qualification.

### `llmwiki/lint/rules/orphan_detection.py`, `llmwiki/references.py`, `llmwiki/backlinks.py`

**N5 — The consolidation is described as behaviour-preserving but changes dedup semantics in three consumers.**
`technical-considerations.md:147` says "Unify the pattern and the anchor-stripping step only. Do not change what any consumer does with the targets it gets," and §3 lists the consolidation as "changes no behaviour". Three sites previously deduped on the *raw* target and then stripped; they now dedup on the *stripped* target:

- `orphan_detection.py:29` — a page containing both `[[a]]` and `[[a#x]]` used to contribute `inbound["a"] = 2`; it now contributes `1`. Harmless today because the rule only tests `== 0`, but the counter is now semantically different from what it was.
- `references.py:148` — `build_index()` used to append two `Reference` rows for `[[a]]` + `[[a#x]]` in one page; now one. `llmwiki references <entity>` output counts change.
- `backlinks.py:112` — `build_reverse_index()` used to emit two `BacklinkEntry` rows for the same referrer; now one, so a rendered `<!-- BACKLINKS -->` block stops listing the same page twice.

All three changes are improvements. None is tested, none is in the CHANGELOG, and all three contradict the "behaviour-preserving" framing the PR body is expected to lean on for the ≤500-line waiver.

*Fix:* add one test each (or one parametrized test) asserting that `[[a]]` + `[[a#x]]` in a single page yields exactly one backlink / one reference / one inbound count, and add a sentence to the CHANGELOG entry noting that duplicate anchor-only variants of the same link now collapse.

### `context/spec/004-topic-page-kind-and-key-facts/`

**N6 — The technical spec was not amended for the search-index change it forbids.**
Two places still assert the opposite of what shipped:

- `technical-considerations.md:192` — "`site/search-index.json`, whose shape `docs/reference/reader-api.md` freezes | **Untouched.** Topic entries are hand-constructed (`build.py:2613`), not a copy of node keys, so new node fields do not leak into the index and no version bump is triggered."
- `technical-considerations.md:254` — "Topic entries in `site/search-index.json` carry **exactly the keys they carry today** — a guardrail against node fields leaking into the frozen reader contract."
- `flow-log.md:59` repeats the same claim as an established code fact.

`build.py:2707` adds `"kind": kind_label(...)` to every topic entry, and `tests/test_108_acceptance.py:288` was written to allow it. The addition is correct — FR11 requires it, `docs/reference/reader-api.md` is a contract-only preview that does not enumerate search-entry keys, and `docs/reference/ui.md:304` documents the new field — but the tech spec is the artefact a future maintainer greps, and it currently says the file was not touched. Under this repo's AWOS flow the spec is amended when behaviour changes, not left to disagree with the code.

*Fix:* amend both rows in `technical-considerations.md` to record the FR11 decision and why it is additive-safe, and add a "Decisions taken" bullet to `flow-log.md` superseding line 59.

### `tests/test_graph_viewer.py`

**N7 — The raised size ceiling leaves 203 bytes of headroom and does not name the tracking issue.**
`tests/test_graph_viewer.py:368-383` raises the guardrail from 41 000 to 43 500. Measured on this branch:

```
len(HTML_TEMPLATE) == 43297   →  203 bytes under the ceiling (0.5 %)
```

That is smaller than the comment block that was just added to the template. The guardrail has stopped being a budget and become a tripwire: the next one-line comment in `HTML_TEMPLATE` fails CI, and the assertion message says only "split the `<script>` into an external .js asset instead of raising this" — it never names **#127**, which `CHANGELOG.md:13` says tracks exactly that work. A contributor who trips it has no pointer.

*Fix:* add `#127` to both the comment block and the assertion message so the failure routes straight to the tracking issue. (Keeping the ceiling at 43 500 is the right call — do not add slack; the point is that the next feature must externalize the script.)

---

## Nits

- **`llmwiki/graph.py:655-658`** — the legend still labels the `other` swatch **"Other"** (`KIND_LABELS`), while `kindLabelOne` (the side panel) and `topics_page.kind_label` (the page chip and the search badge) all call the identical state **"Unclassified topic"**. Three surfaces of the same feature, two names. Consider having the legend use `kindLabelOne` for `other`.
- **`llmwiki/graph.py:657`** — the explanatory comment above `KIND_LABELS` ("Human labels for the wiki folders a node can belong to. Used by the legend and by the Cluster control's collapsed-node captions.") was deleted in this diff while the constant it documented stayed. Nothing replaces it; the new comment below documents `kindLabelOne` instead. Restore it.
- **`llmwiki/graph.py:1325-1331`** — `__KIND_OTHER_LABEL__` is substituted *after* `__GRAPH_JSON__`, so a wiki page whose title or topic name is literally `__KIND_OTHER_LABEL__` would have the token replaced inside the embedded JSON payload, corrupting it. Identical shape to the pre-existing `__SITE_NAV__` / `__SITE_PALETTE__` ordering, so this is not a regression — but reordering so `__GRAPH_JSON__` is substituted *last* would close it for all three at zero cost.
- **`llmwiki/topics_page.py:434`** — `topics/<slug>.html` is still written for project topics, but after `resolve_project_topic_urls()` nothing links to it: not the map, not the search index, not `topics/index.html`, not neighbour lists on other topic pages. Dead output that still lands in `manifest.json` and `sitemap.xml`. It doubles as FR4's fallback surface for a project with no built page, which is a good reason to keep it — but a one-line comment at the write site saying so would stop the next reader filing it as a bug.
- **`llmwiki/topics_page.py:230-233`** — `page_content()` drops *every* leading `# H1` encountered before the first content line (`if level == 1 and not seen_content: continue` never sets `seen_content`), not just the page's own title. A page opening with two consecutive H1s silently loses both. Almost certainly irrelevant in practice; a `break`-style "only the first" guard would be exact.
- **`llmwiki/graph.py:968-980` vs `llmwiki/topics_page.py:_identity_line`** — the panel reads Sessions → Connected topics → Kind → Active → Reviewed; the page reads chip → Active → Reviewed → counts → slug. FR7 asks the panel to "say the same things", which it does; matching the order would make the two read as one design.
- **`CHANGELOG.md:13`** — the entry is a single ~5 000-character paragraph, several times the length of any neighbouring entry including the `BREAKING` one above it. Correct per the no-hard-wrap rule and the content is accurate, but it reads as a design doc rather than a release note. Consider splitting into `Added` sub-bullets (topic pages / project pages / map colours / panel / search badge).
- **`llmwiki/build.py:3294-3309`** — if `write_graph_html()` raises `OSError`/`ValueError`/`RuntimeError`, the `except` swallows it and `build_topic_pages()` never runs, leaving already-written project pages (and search-index entries) pointing at `topics/*.html` that do not exist. Pre-existing exposure for the search index; this diff extends it to project pages. Moving `build_topic_pages()` above `write_graph_html()` inside the same `try` would shrink the window.

---

## Checklist coverage

Every section of `docs/maintainers/REVIEW_CHECKLIST.md` was applied. Sections with no findings are listed so it is clear they were not skipped.

### Meta — one finding, actionable at PR-open time

- **Linked issue** ✅ — #108 throughout; `context/product/roadmap.md:46` flipped to `[x]`; follow-ups #126, #127, #109 correctly filed rather than absorbed.
- **Conventional-commit titles** ✅ — all 8 commits use `feat:` / `fix:` / `docs:` / `test:` with `(#108)` scope.
- **CHANGELOG entry** ✅ — `## [Unreleased] → ### Added`.
- **Tests added** ✅ — 9 new files, 1 792 added test lines, plus extensions to 3 existing suites.
- **AWOS context gate** ✅ — `context/spec/004-…/` and `context/product/roadmap.md` change alongside `llmwiki/`, `tests/`, `docs/reference/`.
- **One concern per PR / ≤500-line target** ⚠️ **action required in the PR body.** Production code alone is +721/−102 across `llmwiki/`; the full diff is +3701/−122. CONTRIBUTING allows exceeding the target only when "the PR body says so explicitly and states that behaviour is unchanged", and `technical-considerations.md:218` pre-committed to exactly that. The PR body must therefore (a) state the overage, (b) state that the §2.7 wikilink consolidation is a prerequisite for §2.6 rather than an unrelated sweep, and (c) — given N5 — say *precisely* which dedup behaviours changed rather than claiming blanket behaviour preservation.
- **CI green** — not yet observable (no PR). Local `ruff` + full `pytest` are green; per `.claude/rules/contributing.md` "After you push", wait on Actions for the head SHA before calling it done.

### Layer boundaries (ARCHITECTURE.md) — no findings

L2 (`build.py`, `render/css.py`, `render/js.py`), L3 (inline viewer JS in `graph.py`) and the wiki-model modules (`topics.py`, `topics_page.py`, `graph.py`) are all touched, which is inherent to a feature that spans map → page → index. No converter or adapter (L0/L6) is touched. `llmwiki/wikilinks.py` is a genuine leaf — `tests/test_wikilinks.py:84` asserts it imports nothing from the package, which is the right guardrail for the "don't elect `graph` or `lint` as owner" argument in `technical-considerations.md:141`. The two deferred imports added (`build.md_to_html` in `topics_page`, `topics_page.KIND_OTHER_LABEL` in `graph.write_html`) both carry `# noqa: PLC0415` with a named cycle, which is the exact exemption CONTRIBUTING allows.

### DECLINED.md — no findings

Nothing in the diff re-proposes a declined idea. Checked specifically against the entries that touch the graph and comparison surfaces: no N-way comparisons, no scraping, no cost estimates, no hybrid search, no forced `_context.md`, no telemetry. The new `comparisons` / `questions` colours add swatches for folders nothing writes into yet, which is a rendering completeness choice, not a re-litigation of the N-way decline.

### Security + privacy — no findings

- **No real session data / machine paths** — grepped the new tests and modules for `/home/…`, `/Users/…` and the maintainer's username: zero hits. Fixtures are synthetic (`Hazel`, `Batching`, `toolkit`, `legacy-app`).
- **No XSS** — this was the section to worry about, since FR3 renders wiki body content into HTML for the first time. It holds up: `md_to_html()` registers `_EscapeRawHtmlPreprocessor` at priority 22 (`build.py:604-610`, the #74 fix), so raw tags in a wiki body are escaped before rendering. Everything the diff constructs by hand is escaped — `kind_chip` (`html.escape`), `_activity_span` / `_reviewed_span` (`html.escape`), `_identity_line`'s slug (`html.escape`), `_topic_links` / `_topic_href` / `render_connected_topics` hrefs (`html.escape(..., quote=True)`), and the viewer's `statRow` (`escapeHtml` on both label and value). `_resolve_wikilinks` deliberately does *not* re-escape the label — correct, because it operates on already-rendered output, and the docstring says so. `render/js.py:1029` additionally *adds* escaping to the palette badge, which was previously unescaped.
- **No network calls at build time** ✅ — no new `urllib`/`http` usage.
- **No new runtime deps** ✅ — every added import is stdlib (`re`, `collections.abc.Collection`) or first-party.
- **Localhost binding / telemetry** — N/A, no server or analytics code touched.
- **Redaction** — N/A, converter untouched.

### Code quality — findings N2, N3 only

Docstrings are present on every new public function (`resolve_project_topic_urls`, `kind_label`, `kind_chip`, `page_content`, `project_connected_topics`, `render_connected_topics`, `project_session_dates`, `strip_anchor`, `wikilink_targets`, `_frontmatter_str`) and are unusually good — they explain the *why*, not the *what*. Type hints are complete and consistent with neighbours. Error handling degrades rather than crashing in the right places: `_backing_page_markdown` swallows `OSError` for a vanished file, `resolve_project_topic_urls` skips a node with no compiled URL rather than raising, and the viewer wraps `topicIdentityRows` in `try/catch → reportGraphError()`, satisfying CONTRIBUTING's "never fail silently in the browser". No dead code left behind — all four `WIKILINK_RE` declarations and all seven hand-rolled `.split("#")[0].strip()` sites are gone, and `tests/test_wikilinks.py:71` greps the package to keep a fifth from appearing.

One design detail worth recording as *correct* rather than as a finding: `topic_kind_lookup()` keeps `kind` folder-derived and says so in a comment citing `docs/UPGRADING.md`. `tests/test_108_acceptance.py:174` proves a pre-#102 `type: entity` + `entity_type: project` page still resolves to `projects` and routes across all four surfaces. That is the single highest-risk compatibility path in the diff and it is properly nailed down.

### Tests — no findings

- Happy path *and* edge cases throughout: absent frontmatter, quoted vs bare `last_updated`, anchor-only `[[#x]]`, empty sections, `##` inside a fenced block, prose-only pages, sparse vaults below `_TOPIC_GRAPH_MIN_NODES`, projects with no built page, unresolvable citations.
- Names describe behaviour (`test_last_updated_quoted_and_bare_render_identically`, `test_project_without_a_site_page_falls_back_to_its_topic_page`).
- Everything is under `tmp_path` with `monkeypatch` on `build_mod.REPO_ROOT` / `SOURCE_ROOT` / `RAW_DIR` / `DEFAULT_OUT_DIR` / `PROJECTS_META_DIR`. Nothing writes under the repo root or touches a real vault — checked every new file.
- `test_wikilinks.py` implements the §2.7 equivalence table exactly as specced, including the explicit `[[#x]]` divergence assertion, before consumers were migrated.
- Gap noted under N1 and N5 (routing of project neighbours; dedup semantics) — both are unguarded, neither is a missing-test-for-shipped-code problem so much as a missing test for a behaviour the spec claimed would not change.

### Docs — findings N6 only

`docs/reference/ui.md` gains a full Topic-pages section with a provenance table that answers FR9's "which information comes from sessions and which from the topic's own page" directly, plus updates to Project detail, Graph (colour table, side panel, tab behaviour), and Search (badge + `type:topic` filter still matching). `docs/reference/reader-shell.md:166` correctly repoints the `WIKILINK_RE` reference at the new home. All markdown is single-line-per-paragraph per the no-hard-wrap rule. The one gap is the un-amended tech spec (N6). `README.md` needs no change — no new CLI, nav link, or file layout.

### Build + runtime smoke — partially applied

Not run against the operator's live vault, deliberately: the review brief forbids mutating `llmwiki` invocations and the operator has a live Obsidian vault. Equivalent coverage comes from the acceptance suite, which drives the real `build_site()` end-to-end against four fixture vaults in `tmp_path` and asserts on emitted HTML — including `test_mixed_vault_completes_and_every_topic_page_opens` and `test_every_topic_page_link_resolves_to_a_real_file`, which are the file-level equivalent of clicking around. Before merge, a maintainer should still run `python3 -m llmwiki build --vault <throwaway>` and open `graph.html`, `topics/index.html`, one entity topic page and one project page with the console open — N1 in particular is a click-through defect that no assertion in the suite catches.
