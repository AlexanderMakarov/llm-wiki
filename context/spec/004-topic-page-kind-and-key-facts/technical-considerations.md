# Technical Specification: Topic pages show what the wiki knows about a topic

- **Functional Specification:** [`functional-spec.md`](functional-spec.md) (approved)
- **Status:** Completed
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

The information FR1–FR3 need already exists on disk; it is discarded on the way to the site. Three functions drop it:

- `scan_pages()` (`llmwiki/graph.py:147`) reads every wiki file in full and returns only `{path, type, title, out_links, site_url}` — the frontmatter dates it already parsed past are thrown away.
- `topic_kind_lookup()` (`llmwiki/topics.py:197`) matches a topic to its backing page, then keeps **only that page's folder name**, discarding which page matched.
- `build_topic_pages()` (`llmwiki/topics_page.py:96`) never opens a backing page at all.

So the plan is not to compute new facts but to stop discarding known ones.

**Layering.** Node metadata stays small and identity-only — kind, the matched page's slug and path, its review date, and session-derived activity dates. Page *content* is never put on a node: `graph.html` embeds the entire graph as inline JSON, so anything on a node is downloaded by every viewer before the map draws. `build_topic_pages()` opens the backing page at render time instead.

**Ownership of the project URL.** `build_topic_graph()` cannot know which project pages the build actually wrote — it does not see `groups` and has no `out_dir`. It therefore records *which project a topic matched* and leaves URL resolution to a separate pass in `build.py`, which knows both.

**Build ordering.** `render_project_page()` runs at `build.py:3083`; `build_topic_graph()` at `build.py:3148`. FR5 needs topic data on project pages, so the graph construction moves above the project loop. It was already hoisted once for the search index (`build.py:3143` comment) and is wrapped in a `try/except` that degrades to `topic_graph = None`, so the precedent and the failure path both exist.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 `scan_pages()` — carry the dates it already reads past

`llmwiki/graph.py:147`. Returns `dict[slug, dict]`; add two keys. Purely additive — every existing caller keeps working.

| Key | Source | Notes |
| --- | --- | --- |
| `last_updated` | frontmatter `last_updated` | `None` when absent — no fallback invented here |
| `date` | frontmatter `date` | the session's own date on a source page; distinct from `last_updated`, which is when synth ran |

Replace the ad-hoc title regex (`graph.py:176`) with `parse_frontmatter()` from `llmwiki/_frontmatter.py` so all three fields come from one parse of text already in memory. Title-extraction behaviour must not change — a page with no frontmatter still falls back to the slug.

### 2.2 `topic_kind_lookup()` — return the matched page, not just its folder

`llmwiki/topics.py:197`. Today `dict[str, str]` mapping lowercased slug/title → folder name. Becomes a mapping to a small record. Both this function and `resolve_topic_kind()` are used **only inside `topics.py`** and no test references either by name, so the signatures are free to change.

| Field | Meaning |
| --- | --- |
| `kind` | wiki folder — unchanged semantics |
| `slug` | the matched page's filename stem — this is what FR4 needs and what is thrown away today |
| `path` | page path relative to the wiki root's parent, for the render-time read |
| `last_updated` | the page's own review date, or `None` |
| `site_url` | the page's compiled URL as `scan_pages` already computed it, or `None` |

`resolve_topic_kind()` becomes `resolve_topic_page()` returning that record or `None`, keeping the existing precedence: canonical spelling first, then aliases in sorted order.

**`kind` stays folder-derived — do not "improve" it to read frontmatter.** `scan_pages` sets a page's type from `rel.parts[0]`, its directory. This is what makes pre-#102 vaults work: `docs/UPGRADING.md` records that project pages created before that change keep `type: entity` + `entity_type: project` indefinitely, and a frontmatter-based lookup would mis-kind every one of them. The folder is the schema.

**`site_url` already exists and is already correct for projects.** `_compute_site_url()` (`llmwiki/graph.py:107`) maps `wiki/projects/<slug>.md` → `projects/<slug>.html` today; the value is computed on every scan and then discarded along with the rest of the record. Carry it rather than reconstructing the path.

### 2.3 `build_topic_graph()` — node and session-meta fields

`llmwiki/topics.py:262`. Node keys added alongside the existing `kind`:

| Key | Value | Absent when |
| --- | --- | --- |
| `wiki_slug` | matched page's stem | no page describes the topic |
| `wiki_path` | matched page's path | ditto |
| `wiki_site_url` | matched page's compiled URL | no page, or the page compiles to none |
| `last_updated` | matched page's review date | no page, or page records none |
| `first_seen` | earliest `date` among the topic's sessions | no session carries a date |
| `last_seen` | latest `date` among the topic's sessions | ditto |

`sessions_meta` (`topics.py:295`) gains `date` per session so first/last-seen can be derived without a second scan. Absent fields are omitted or `None` — never a placeholder string, per FR2.

### 2.4 Project URL resolution — a separate pass

New public function in `llmwiki/topics.py`:

```
resolve_project_topic_urls(graph, built_project_slugs) -> int
```

For every node with `kind == "projects"`, adopt the backing page's already-computed URL — carried on the node as `wiki_site_url`, kept distinct from the node's own `site_url` so the topic-page URL is never clobbered — **when `wiki_slug` is in `built_project_slugs`**. Returns the count rewritten. Nodes whose project has no built page keep `topics/<slug>.html` — FR4's fallback, which fires when a `wiki/projects/*.md` page exists but no session was recorded against it.

The membership test is the whole job: the URL is already correct, but `wiki/projects/` is written by `ensure_project_stubs()` while `site/projects/` is written from session groups, so the two sets can differ. This mirrors `_verify_site_url()` (`graph.py:193`), which exists for exactly this class of "don't offer a link that 404s" problem (#328) — but keys on the built project set rather than probing the filesystem, since `build.py` already holds `groups`.

Called once from `build.py` with `set(groups)` after the graph is built and **before** `write_graph_html()`, `build_topic_pages()`, and the project page loop, so the viewer's double-click target, the static page, and the project page all agree.

### 2.5 `build.py` — ordering and the project page section

- Move the `build_topic_graph()` block (currently `build.py:3146-3153`) above the `render_project_page()` loop at `build.py:3083`. `use_topic_graph` / `_TOPIC_GRAPH_MIN_NODES` logic moves with it unchanged.
- Call `resolve_project_topic_urls()` immediately after.
- `render_project_page()` (`build.py:1372`) takes a new optional parameter carrying the project's connected topics — `list[tuple[str, int]]`, already the shape `_neighbors()` returns. Default empty so existing callers and tests are unaffected.
- Render a Connected topics section immediately above `<h2>Main sessions …</h2>` in the `body` f-string (`build.py:1506`). Empty list → no section and no heading (FR5).

**Do not confuse this with the existing topic chips.** `get_project_topics()` renders `topics:` frontmatter or a session-tag fallback in the hero strip; FR5's list is graph co-occurrence. Different data, different place on the page.

### 2.6 `topics_page.py` — identity line and page content

**Identity line** — a helper rendering FR1's line from node fields: kind chip, dates, connection count, session count, slug. Every element is omitted entirely when its field is absent; no labels without values (FR1, FR8).

**Content extraction** — new helper taking raw page text and returning the markdown to render:

1. Strip frontmatter (`parse_frontmatter`).
2. Drop the leading `# H1` — the page already shows the title.
3. Drop the `## Connections` and `## Sessions` sections (heading through to the next `##` or end) — the topic page renders both itself, from the graph.
4. Return what remains; empty/whitespace-only → `None`, so no heading is emitted.

This is deliberately heading-agnostic apart from those two exclusions: it renders intro prose, `## Key Facts`, and any section a curator added, and keeps working if #109 renames or replaces `## Key Facts`.

**Rendering** — `md_to_html()` from `llmwiki.build`, via the module's existing deferred-import block (`topics_page.py:101`, already `# noqa: PLC0415` for the `build ↔ topics_page` cycle). No new import pattern.

**Wikilinks** — Key Facts bullets carry `[[source-slug]]` citations. Resolution order, applied after markdown rendering:

| Target matches | Becomes |
| --- | --- |
| a topic in the graph | link to `<topic-slug>.html` (sibling in `topics/`) |
| a session with a `site_url` | link to `../<site_url>` |
| nothing | plain text — the link markup is removed, the text kept (FR3) |

Built on the consolidated helper from §2.7, not a fifth copy of the pattern.

Content renders **above** Connected topics (FR3).

### 2.7 Consolidate the four `[[wikilink]]` pattern declarations

In scope because §2.6 needs wikilink parsing and the alternative is adding a fifth copy.

**Current state.** Three declarations are byte-identical: `llmwiki/graph.py:30`, `llmwiki/lint/__init__.py:36`, and `llmwiki/backlinks.py:101` (private `_WIKILINK_RE`). The fourth, `llmwiki/graphify_bridge.py:77`, is a **function-local** variable whose pattern excludes `#` from the capture and consumes the anchor inside the regex. Meanwhile seven call sites strip anchors by hand: `topics.py:140`, `topics.py:258`, `candidates_harvest.py:91`, `backlinks.py:116`, `lint/rules/orphan_detection.py:29`, `lint/rules/link_integrity.py:40`, `references.py:150`.

So the duplication is not only the pattern — it is the same anchor-stripping step written eight different times, once inside a regex and seven times after it.

**Target.** A new leaf module `llmwiki/wikilinks.py` owning both:

| Export | Contract |
| --- | --- |
| `WIKILINK_RE` | the canonical pattern — the byte-identical form the three agreeing declarations use |
| `strip_anchor(target)` | one already-extracted target without its `#section` anchor, trimmed |
| `wikilink_targets(text)` | set of link targets from markdown, anchors stripped, empty targets excluded |

Two levels because not every consumer holds the markdown text or wants a set. Three of the seven hand-rolled sites need `strip_anchor` rather than `wikilink_targets`: `topics.py:140` and `topics.py:258` iterate `page["out_links"]`, which `scan_pages` already extracted; `graphify_bridge` iterates `findall` as a **list** because it emits one edge per occurrence, so collapsing to a set would drop edges from `graph.json`; and `lint/rules/link_integrity.py` quotes the **raw** target in its operator-facing message and dedups on raw, so a set of stripped targets would change both the message text and the issue count. Only sites that genuinely want distinct page names take `wikilink_targets`.

A dedicated leaf module rather than promoting one of the existing homes: `graph` and `lint` are each imported by different consumers of this pattern, so electing either as owner creates an import edge between subsystems that do not otherwise depend on one another. Nothing imports back out of `wikilinks`, so no cycle is possible.

**Migration.** Point every declaration and consumer at the new module and delete the copies. Per CONTRIBUTING ("prefer importing helpers from the owning module over high-level facade re-exports"), update the importers rather than leaving `graph`/`lint` re-exporting — `synth/pipeline.py:40` imports from `llmwiki.graph`; `candidates_harvest.py:21` and `references.py:35` from `llmwiki.lint`. `references.py:22` has a docstring naming `llmwiki.lint.WIKILINK_RE` that must be updated with it. Replace the seven manual `.split("#")[0].strip()` sites with `wikilink_targets()` where they iterate link targets.

**Behavioural note.** `graphify_bridge`'s variant and canonical-plus-strip agree on every ordinary form (`[[a]]`, `[[a|b]]`, `[[a#b]]`, `[[a#b|c]]`, `[[a|b#c]]`). They differ only on a target that is nothing *but* an anchor (`[[#x]]`): the local variant does not match at all, canonical-plus-strip yields an empty target. Both are discarded downstream; the tests below pin the behaviour so the equivalence is asserted rather than assumed.

**Scope discipline.** Unify the pattern and the anchor-stripping step only. Do not change what any consumer does with the targets it gets.

### 2.8 Viewer — colours and panel

`llmwiki/graph.py`, embedded CSS + JS.

**Colours.** Add four variables to *both* theme blocks (`graph.py:310` dark, `graph.py:328` light) and four entries to the `colors` map (`graph.py:615`):

| Kind | Value | Note |
| --- | --- | --- |
| `projects` | `#db2777` | magenta |
| `questions` | `#0891b2` | cyan |
| `comparisons` | `#b45309` | brown |
| `other` | `#65a30d` | lime |

Values are the palette recorded in FR6. Red is excluded because `--g-orphan` and `--g-search-match` already hold it in both themes (`graph.py:323`, `326`, `341`, `344`) — the tests below assert no kind colour collides with either.

`kindColor()` keeps `colors.topic` as the last-resort fallback for unknown strings.

**Side panel.** `showTopicPanel()` (`graph.py:908`) gains a kind row and a freshness row after the existing Sessions / Connected topics stats, both omitted when the node lacks the field (FR7). Existing `escapeHtml()` applies to every interpolated value.

**Error surfacing.** The panel already runs inside the viewer's normal flow; any new failure path uses `reportGraphError()` (`graph.py:632`), which routes to `window.__llmwikiReportError` — per CONTRIBUTING's static-site error handling rule.

### 2.9 Documentation (FR9)

| File | Change |
| --- | --- |
| `CHANGELOG.md` | entry under `## [Unreleased]` |
| `docs/reference/ui.md` | **new** topic-pages section — the file documents every other site surface; Projects and Graph sections updated for the connections list and per-kind colours |

---

## 3. Impact and Risk Analysis

### Existing vaults — no migration, no re-sync

**Nothing this change needs is stored in the vault.** Every added field is derived at build time from frontmatter already on disk or from a file's own location, so an untouched vault picks up the new pages on its next `build` with no `sync` or `synth` re-run and no edit to `wiki/`.

| Compatibility question | Answer |
| --- | --- |
| Pages with no frontmatter, or malformed frontmatter | `parse_frontmatter` returns `({}, text)` uniformly and never raises; the title falls back to the slug as it does today |
| Pages with no `last_updated`; sources with no `date` | Degrade to *absent*, which is FR2/FR8's specified behaviour. Legacy vaults exercise the same path the FR8 tests cover — this is the normal case, not a compatibility shim |
| Project pages predating #102 (`type: entity` + `entity_type: project`) | Unaffected — kind comes from the folder, never from frontmatter. See §2.2 |
| `last_updated` written quoted vs bare | Both forms exist in real vaults (`synth/pipeline.py:631` quoted, `:1042` bare); `_parse_scalar` strips quotes |
| A stale `graph/graph.json` written by an older llmwiki | Cannot affect anything — the file is write-only. Nothing reads it back, and `build` reconstructs the graph in memory every run |
| `site/search-index.json`, whose shape `docs/reference/reader-api.md` freezes | Additive only, and deliberately so. Topic entries are hand-constructed (`build.py:2613`), not a copy of node keys, so no node field leaks in by accident. FR11 then adds exactly one field by hand — `kind`, carrying the same singular label the chip uses. That is additive-safe: `reader-api.md` is a contract preview that never enumerates topic-entry keys, `type` stays `topic` so the documented `type:topic` filter still matches every topic result, and a reader that does not know the field ignores it. No version bump is triggered |
| Other `build_topic_graph` consumers — `synth/pipeline.py:297` (vocabulary prompt), `topics_consolidate.py:54` (merge candidates) | Both read named keys only and never iterate or serialize whole nodes; added keys are inert to them |
| Other commands | `sync`, `synth`, `lint`, `candidates` and the MCP server are untouched except by the §2.7 consolidation, which is behaviour-preserving. MCP does not read the topic graph at all |

The one thing legacy vaults genuinely lack — a `last_updated` on project pages — is what FR2 exists to solve, and it is solved by deriving freshness from sessions rather than by migrating stubs.

**Verification:** build the repo's own demo vault (which predates every field here) and a fixture vault carrying none of the optional frontmatter, and assert both render.

### System Dependencies

- `scan_pages()` is read by `topic_kind_lookup`, `build_graph`, and the topic vocabulary. Changes are additive; the title fallback is the one behaviour that must not regress.
- Moving `build_topic_graph()` earlier changes the order of build-time stdout. Tests asserting on build output ordering may need updating.
- `render_project_page()` gains an optional parameter — existing call sites and tests keep working unchanged.
- The §2.7 consolidation reaches into lint rules, synth, backlinks, references, harvest, and the graphify bridge. It changes no behaviour, but it is the widest-reaching part of this change and every touched consumer is covered by the existing suite.

### Potential Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| **Reading every backing page at render time** adds file I/O proportional to topic count. | Only pages that actually back a topic are read, once each, during a build that already reads the whole vault. Measure on the throwaway vault if topic count is large. |
| **Hoisting the graph build** could change behaviour if project rendering depended on state the graph build mutates. | `build_topic_graph()` is pure CPU over the wiki and writes nothing. The existing `try/except` keeps a graph failure from breaking project pages either way. |
| **`use_topic_graph` false (<5 nodes)** means no topic pages and no node data. | Project pages must render with no Connected topics section, not with an empty one. This is FR8's cheapest test and the demo vault's actual state. |
| **Page content is rendered into HTML.** | `md_to_html()` is the same trusted pipeline used for session bodies; wiki content is already treated as trusted input elsewhere in the build. Wikilink resolution escapes attributes it constructs. |
| **`#dc2626` collision** would have shipped undescribed topics looking like orphans. | Caught pre-implementation; lime substituted, deviation recorded above. |
| **Graph payload growth** — the reason content stays off nodes. | Added fields are short strings; a rough ceiling of ~120 bytes/topic is the design constraint. |
| **The wikilink consolidation silently changes link parsing** across lint, synth, backlinks and harvest — a regression here corrupts the graph and the lint report at once. | The canonical pattern is the byte-identical form three of the four declarations already use, so only `graphify_bridge` changes shape. Equivalence tests pin both against a shared case table before consumers are migrated. |
| **Diff size** — the consolidation touches ~10 files on top of the feature, against CONTRIBUTING's ≤500-line target. | It is a prerequisite for §2.6 rather than an unrelated sweep, so it stays one concern. If the total still exceeds the target, the PR body must say so and state that the refactor is behaviour-preserving, per CONTRIBUTING's mechanical-diff clause. |

---

## 4. Testing Strategy

Existing suites to extend: `tests/test_topics.py`, `tests/test_graph_viewer.py`, `tests/test_project_topics.py`, `tests/test_topic_graph_sparse_fallback.py`.

**Unit**

- `scan_pages()` returns `last_updated` / `date` when present and `None` when absent; title fallback unchanged for a page with no frontmatter.
- `resolve_topic_page()` matches on canonical spelling, falls back to aliases in order, returns `None` when nothing matches.
- `build_topic_graph()` node carries `wiki_slug` / `wiki_path` / `last_updated` / `first_seen` / `last_seen`, and omits them for a topic with no backing page.
- `resolve_project_topic_urls()` rewrites only project nodes whose slug is in the built set; leaves unmatched project nodes on their topic URL; returns the count.
- Content extraction: drops frontmatter, H1, `## Connections`, `## Sessions`; keeps intro prose, Key Facts, and other sections; returns `None` for a page with nothing left.
- Wikilink resolution: topic target → sibling topic page; session target → session URL; unresolvable → plain text with markup removed.

**Consolidation equivalence (§2.7)** — a shared case table covering `[[a]]`, `[[a|b]]`, `[[a#b]]`, `[[a#b|c]]`, `[[a|b#c]]`, `[[#x]]`, and a line holding several links:

- `wikilink_targets()` returns anchor-stripped, trimmed targets for every case.
- The canonical pattern plus stripping agrees with `graphify_bridge`'s retired local variant on every ordinary form, and the `[[#x]]` divergence is asserted explicitly rather than left implicit.
- No `WIKILINK_RE` declaration survives outside `llmwiki/wikilinks.py` — a guardrail test greps the package, so a future fifth copy fails CI instead of accumulating.

**Integration (build a vault, assert on emitted HTML)**

- Entity topic page shows kind chip, dates, counts, slug, and its Key Facts above Connected topics.
- Project topic node's `site_url` points at `projects/<slug>.html`; a project page with no sessions falls back to its topic page.
- Project page renders Connected topics immediately above Main sessions.
- Topic with no backing page renders with no chip, no review date, and **no empty heading anywhere** — assert the absence of `<h2>` immediately followed by its closing section.
- A vault below `_TOPIC_GRAPH_MIN_NODES` builds cleanly with no topic pages and no Connected topics section on project pages.

**Backward compatibility (§3)**

- A vault whose pages carry none of the optional frontmatter — no `last_updated`, no `date` — builds and renders every topic page, with no date shown and no empty heading.
- A project page written in the pre-#102 shape (`type: entity` + `entity_type: project` under `wiki/projects/`) still resolves to `kind == "projects"` and routes to its project page.
- `last_updated` parses identically whether written quoted or bare.
- Topic entries in `site/search-index.json` carry the keys they carry today plus the single `kind` field FR11 specifies, and nothing else — a guardrail against node fields leaking into the frozen reader contract on top of the one addition that was decided. `type` stays `topic`, so the documented `type:topic` filter is unaffected.

**Viewer (string assertions on generated `graph.html`, as existing graph tests do)**

- All four new CSS variables present in both theme blocks; no two kind colours equal; no kind colour equals `--g-orphan` or `--g-search-match` in either theme.
- `colors` map has an entry per kind in `TOPIC_KIND_FOLDERS` plus `other`.
- `showTopicPanel()` emits kind and freshness rows, and omits them when the node lacks the fields.

**Gate:** `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` green before push.
