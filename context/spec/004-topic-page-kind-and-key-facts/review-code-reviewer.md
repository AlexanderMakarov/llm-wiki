# Code review — #108 topic page kind, dates and Key Facts

**Scope reviewed:** `git diff origin/main...HEAD` (8 commits, 36 files, +3701 / -122) on branch `feat/108-topic-page-kind-and-key-facts`.

Every changed line was read. Verification run locally in the worktree:

- `python3 -m pytest tests/ -q` — all pass (no failures, only pre-existing skips)
- `ruff check llmwiki tests scripts` — clean
- Generated a topic page from a synthetic vault and inspected the emitted HTML
- Exercised `page_content()` directly against edge-case page shapes

**Verdict:** approve with changes. No security issues, no data-loss-to-`raw/` risk, no new runtime deps, no vault/machine-specific detail leaked. Three findings at or above the reporting threshold; two are real defects in the new rendering path, one is a process-gate violation.

---

## Critical (90-100)

None.

---

## Important (80-89)

### 1. Rendered wiki page content on topic pages sits outside the `.content` CSS scope — tables and code blocks lose their overflow guards (confidence 85)

**File:** `llmwiki/topics_page.py:410-419` (the `content_block` wrapper), with `llmwiki/render/css.py` (no rule added for `.topic-page-content`).

`build_topic_pages()` now emits the backing page's markdown as:

```python
'<div class="topic-page-content">\n'
+ _resolve_wikilinks(md_to_html(page_md), topic_index, sessions_meta, node_urls)
+ "\n</div>\n"
```

Every prose style in `llmwiki/render/css.py` is scoped to `.content` (`.content p`, `.content ul`, `.content h2/h3`, `.content table`, `.content pre`, `.content blockquote`, `.content code`). `.topic-page-content` has no rule at all, and neither `.topic-page` nor `.container` supplies a fallback — `.container` is only `max-width: 1080px; margin: 0 auto; padding: 0 24px;`.

Verified by generating a topic page from a synthetic entity page containing a table, a fenced Python block and a blockquote. The emitted HTML is bare `<table>`, `<pre><code class="language-python">`, `<blockquote>` inside `<div class="topic-page-content">`, with no ancestor carrying `.content` or `.article`.

Concrete consequences:

- `.content table { display: block; overflow-x: auto; }` and `.content pre { overflow-x: auto; }` are exactly the responsive guards that keep wide content from blowing out the page. Without them a wide table or a long code line on a topic page forces horizontal scroll on the whole document.
- `.article pre code.hljs` background/border styling does not apply, so highlighted blocks will not match the rest of the site.
- The JS enhancements are also scoped and therefore silently skip this content: `llmwiki/render/js.py:687` (`.content pre` → copy-code buttons), `:1862` (`.content h2[id]` → deep-link anchors), `:1495` (`.content a`). The `toc` extension is emitting heading `id`s (confirmed: `<h2 id="key-facts">`) that nothing will ever link to.

This also touches the PR checklist boxes 14 (UI verified light + dark) and 15 (a11y / responsive), which a wide-table overflow would not pass.

**Suggested fix:** add `content` to the wrapper's class list (`<div class="content topic-page-content">`) so the existing prose rules and JS hooks apply, and check the resulting heading sizes against the page's own `<h2>Connected topics</h2>` — `.content h2` carries a bottom border, so the two `h2` families should be reconciled deliberately rather than by accident.

### 2. `page_content()` silently discards content when a leading `# H1` follows an omitted `## Connections` / `## Sessions` section (confidence 82)

**File:** `llmwiki/topics_page.py:206-233` (`page_content`).

The H1-dropping branch `continue`s before the branch that resets `skipping`:

```python
if level == 1 and not seen_content:
    continue  # the page's own title — the hero already shows it
# Only a heading at `##` or above closes a section; a `###`
# subsection belongs to whichever section encloses it.
if level <= 2:
    skipping = title in _OMITTED_SECTIONS
```

A dropped H1 therefore never closes an open omitted section. Because a line inside an omitted section also never sets `seen_content`, the "leading H1" state persists past the omitted section, and everything between the H1 and the next `##` heading is discarded.

Reproduced directly:

```python
page_content('---\nt: 1\n---\n## Connections\n- [[X]]\n\n# Hazel\n\nImportant prose.\n\n## Key Facts\n- a\n')
# -> '## Key Facts\n- a'
```

`# Hazel` and `Important prose.` are gone. The same shape without the leading `## Connections` keeps both. A second, equally silent variant: `# Title` → `## Connections` → `# Related Work` → prose also loses `# Related Work` and the prose that follows it, because `seen_content` is still `False` when the second H1 is reached.

This is a content-loss path on a rendering surface whose whole point is "entity and concept page content now reaches a reader for the first time", and it fails without any warning. Likelihood is low for canonically formatted pages (CLAUDE.md's entity format puts `## Connections` last), which is why this is Important rather than Critical — but hand-curated pages do reorder sections, and nothing detects it.

**Suggested fix:** reset the section state before skipping the title, e.g. handle the `level <= 2` reset for every heading and only then decide whether the H1 line itself is emitted:

```python
if level <= 2:
    skipping = title in _OMITTED_SECTIONS
if level == 1 and not seen_content:
    continue
```

Add a regression test for both shapes above; the current `tests/test_topic_page_content.py` (16 tests) does not exercise an H1 that follows an omitted section.

### 3. CONTRIBUTING PR-size and one-intent rules (confidence 88)

**Files:** whole branch.

- CONTRIBUTING "PR size — **≤500 lines of diff**. If the PR gets larger than that, the reviewer will ask you to split." This branch is +3701 / -122. Even excluding tests and `context/` spec docs, `llmwiki/` alone is +721 / -102 (823 lines).
- CONTRIBUTING TL;DR rule 1, "One concern per PR." The branch carries the #108 feature *and* an unrelated-in-kind refactor: the new leaf module `llmwiki/wikilinks.py` plus the de-duplication of four `WIKILINK_RE` declarations and seven manual anchor-strip sites across `backlinks.py`, `candidates_harvest.py`, `graphify_bridge.py`, `lint/__init__.py`, `lint/rules/*`, `references.py`, `synth/pipeline.py`, `topics.py`. `context/.../technical-considerations.md` frames it as a §2.6 prerequisite, and the flow-log records it was pulled in at the user's direction — but it is a self-contained `refactor:` that stands on its own and would make a clean separate PR.

**Suggested fix:** if the branch has not shipped yet, split the wikilink consolidation (commit-sized, independently green, its own `tests/test_wikilinks.py`) into a preceding `refactor:` PR and rebase #108 on it. If it has already shipped, note the waiver explicitly in the PR body per the checklist convention rather than leaving the box silently unchecked.

---

## Checked and found correct

Recording these so the next reviewer does not redo the work:

- **Wikilink consolidation is behaviour-preserving.** `graphify_bridge.py` was the one site whose old pattern differed (`[^\]|#]+?` with the anchor consumed inside the regex); `WIKILINK_RE` + `strip_anchor()` produce the same target set for every ordinary form, and the one divergence (`[[#x]]`) is covered by an explicit test. The `!target` guard added at `graphify_bridge.py:137` correctly handles the anchor-only case the old pattern simply never matched. No `WIKILINK_RE` declaration survives outside `llmwiki/wikilinks.py`, and the guardrail test enforces it.
- **`scan_pages()` frontmatter switch.** Replacing the ad-hoc `^title:` regex with `parse_frontmatter` narrows title extraction to the frontmatter block, which is the intended tightening; the slug fallback and quoted/bare `last_updated` equivalence are both covered by new tests. `_frontmatter_str` correctly rejects list/dict values and normalises `_parse_scalar`'s int coercion back to text.
- **Project routing correctness.** `resolve_project_topic_urls()` gates on `wiki_slug in built_project_slugs`, and both sides of that comparison are the same identifier: `_compute_site_url` derives `projects/{slug}.html` from the wiki page stem, and `set(groups)` keys are the session-group project slugs that `render_project_page` writes files for. The 404-avoidance reasoning in the docstring holds. `topic_nodes` is the same list object the search index receives, so the in-place mutation reaches it.
- **Build ordering.** Hoisting `build_topic_graph()` above the project-page loop is safe: `ensure_project_stubs()` (the only writer into `wiki/projects/`) runs earlier still, and nothing between the old and new call sites mutates `wiki/`.
- **`_drop_empty_sections()`** is correct for nested cases, including a `##` whose only child `###` was itself empty. Fence tracking correctly suspends heading detection and correctly runs even inside a skipped section.
- **Relative-URL construction.** `_topic_href()` (`topics/` prefix stripped for siblings, `../` otherwise) and `render_connected_topics()` (`../topics/`) are both correct for their emitting directory.
- **No XSS introduced.** `_resolve_wikilinks` runs on `md_to_html` output where link text is already escaped, and escapes only the href it constructs (`quote=True`). Raw-HTML passthrough in wiki bodies is pre-existing `md_to_html` behaviour, unchanged here.
- **Graph template budget.** `len(HTML_TEMPLATE)` is 43,297 against the raised 43,500 ceiling — 203 bytes of headroom, matching the CHANGELOG's statement that this is the last stretch and #127 must land next.
- **Docs.** `docs/reference/ui.md` accurately describes the shipped click/double-click behaviour (single click still `window.open` in page mode at `graph.py:913`, double-click at `:933`; the side panel, session links and context-menu **Open** now navigate in-tab). `docs/reference/reader-api.md` does not enumerate topic-entry fields, so the additive `kind` field needed no change there. `context/` is updated, CHANGELOG has an Unreleased entry, roadmap ticked.

---

## Below the reporting threshold (noted, not blocking)

- `.palette-results .result-type` is `text-transform: uppercase` at `0.68rem`; an unclassified topic now badges `UNCLASSIFIED TOPIC`, which is roughly 4× the width of the old `TOPIC`. Worth an eyeball in the palette before release. (confidence 60)
- `build.py` imports the private `_neighbors` from `topics_page`. Either promote it or add a thin public wrapper. (confidence 55)
- A project page's own Connected topics list hardcodes `../topics/<slug>.html` and so does not apply the project routing that every other surface applies. It is not a 404 (topic pages are still written for project nodes) and `ui.md` documents it this way, so it reads deliberate — but it is the one surface where a project topic does not route to its project page. (confidence 50)
- `_identity_line` emits `1 connected topics` / `1 sessions`; `build.py` already has `_pluralize`. Pre-existing wording carried forward. (confidence 45)
