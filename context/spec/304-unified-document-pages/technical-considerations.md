# Technical Specification: Complete documents on one site page

- **Functional Specification:** [`functional-spec.md`](functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger
- **Issue:** [#305](https://github.com/AlexanderMakarov/llm-wiki/issues/305)

---

## 1. High-Level Technical Approach

All work stays in **L2 Site** (build + generated payloads) and **L3 Viewer** (static HTML/CSS/JS). No changes to `raw/`, `wiki/`, synth, or add-doc storage (#311 remains separate).

**Strategy:** introduce one build-time **logical document** model shared by (a) unified reading pages, (b) `search-index` `type:"document"` entries, and (c) the Documents sidebar tree. Fix today’s incorrect “whole top-level folder = one document” heuristic so `--project` multi-doc folders stay separate. Prefer **one catalog** (`search-index` document entries) for identity/titles/filter; keep `documents-tree.json` only as a **nested layout** of those same leaves (same titles/hrefs/ids). Client filter reuses `__llmwikiLoadIndex` (or the document subset already loaded with the tree) — do not invent a third JSON schema.

`★ Compact rule:` one grouping function → many consumers; no parallel title/URL logic.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Logical document model (shared)

**Where:** `llmwiki/raw_docs_site.py` (extend/replace `group_documents` / `DocEntry`).

**Grouping rule (assumption — replaces folder-as-document):**

Within each directory under `raw/docs/`:

1. Partition files by **base slug**: stem with trailing `-\d{2}` removed (matches `add_doc` chunk naming `<slug>-NN`).
2. Each base-slug group is one logical document; sort parts by stem / numeric suffix.
3. Root-level single files remain standalone documents.
4. Prefer cleaned title from `clean_chunk_title(first_part.title)`; date = max of part dates; `content_sha256` may agree across parts but is not required for grouping (legacy docs may lack it).

**`DocEntry` (or renamed `LogicalDocument`) fields:**

| Field | Purpose |
|---|---|
| `id` | Stable id, e.g. `document:<dir>/<base-slug>` (posix) |
| `title` | Readable title (no `(part i/N…)` suffix) |
| `url` | Canonical site path of unified HTML |
| `parts` | Ordered list of `RawDocFile` (or rel paths) |
| `folder_parts` | Parent path segments for tree nesting |
| `date`, `source_label` | As today for Recent |

**Consumers that must call this once per build:** Recent list, `build_search_index` document loop, `write_documents_tree`, unified page writer, part→canonical map.

### 2.2 Canonical URL and unified page HTML

**Canonical URL (assumption):** `documents/<parent-path>/<base-slug>.html` where `<parent-path>` is the directory under `raw/docs` and `<base-slug>` is the group key. For a single-file doc already named `<base-slug>.md`, this matches today’s path. For multi-part docs currently only exposing `<slug>-01.html` etc., the unified page is the new canonical; part URLs become stubs (below).

**Writer:** extend `render_document_pages` (or add `render_unified_document_pages`) in `raw_docs_site.py`, invoked from `build.py` `build_site`.

**Page body:**

- Concatenate part bodies in order into one article.
- Strip per-part breadcrumb lines / repeated H1-equivalent chrome that `add_doc` injects (`Part i of N of **Title**`).
- Emit section anchors: prefer existing headings; if a part has no usable heading, emit a stable anchor from part index / subheading (e.g. `part-03`) for deep links.
- Hide repeated generated part titles in the reading chrome (functional spec).
- Keep sidebar mount + provenance/sources block behavior, keyed off the logical doc (first part’s raw path or union of provenance — prefer first part + note multi-part in UI only if already patterned elsewhere; do not invent a new provenance product).

**Sibling `.md`:** keep copying source parts as today for FR2/raw fallback where needed; canonical reader is HTML.

### 2.3 Old part URLs (no silent 404)

**No HTTP redirects** (site is often `file://`). For each non-canonical part path that previously had a full page:

- Emit a **small stub HTML** at the old `documents/…/<slug>-NN.html` that:
  - Immediately navigates to `canonicalurl#part-anchor` via `<meta http-equiv="refresh">` and/or inline script (both, for stubborn browsers), and
  - Contains a visible fallback link (CONTRIBUTING: never fail silently).

Do **not** leave full duplicate article bodies on part URLs (avoids two “complete” pages).

### 2.4 Search index (universal catalog for documents)

**Where:** `llmwiki/build.py` `build_search_index` document loop (~2820).

**Change:** emit **one** meta entry per logical document:

```text
id:    DocEntry.id
url:   canonical unified HTML
title: cleaned readable title
type:  "document"
date:  …
body:  plain text from assembled content (cap ~300–1200 chars, same spirit as today)
```

Optional (only if needed for section deep-links from search without a second index): a compact `anchors` or rely on client opening `url` / `url#…` when match metadata exists. Prefer minimal frozen-key discipline — if tests pin document entry keys, extend deliberately and update those tests.

Ctrl+K already filters with `type:document`. After this change, multi-part docs stop flooding the palette.

### 2.5 `documents-tree.json` — nested layout only

**Keep the file** (announced in `docs/reference/reader-api.md`, used on Raw / Home / document pages). **Change its leaves** to logical documents:

```text
DocFile leaf: { id, label, href, rel? }
  label = readable title
  href  = canonical unified URL
  id    = same as search-index document id
```

Folders remain path segments (`folder_parts`). Multi-part chunks are **not** separate leaves.

Build tree from the same `LogicalDocument` list (fold into folder nodes) — do not rescan titles differently from search-index.

### 2.6 Viewer: filter, ancestors, highlight

**Where:** `llmwiki/render/js.py` (doctree IIFE), `llmwiki/render/css.py` for highlight style.

**UI:** filter `<input>` under `.doctree-title` on `[data-doctree-mount]`.

**Matching (assumption):** case-insensitive; collect leaves whose `label` starts with or contains the query; sort **starts-with first**, then contains; render inside remaining tree structure.

**Tree filtering:** show a folder if any descendant leaf matches; expand ancestors of matches; hide folders/leaves with no matches. Empty → **No documents match**.

**Highlight:** wrap the first (or all non-overlapping) case-insensitive substring match(es) in the leaf label with `<mark class="doctree-filter-hit">` (or existing mark pattern if one exists).

**Catalog reuse (refined 1):**

- Preferred: on mount, call `__llmwikiLoadIndex`, take `type==="document"` entries as the authority for id/title/url; intersect/join with tree leaves by `id` (tree supplies folder nesting). If index fails to load, fall back to tree labels only and surface the shared error pattern (page-visible, not console-only).
- Alternative if join is too heavy on first paint: tree leaves already carry the same id/title/url written at build time from the shared model — filter operates on tree data, and search-index is guaranteed identical by build tests (same helper). Still **one build-time catalog**, two serializations. Acceptable under FR if build tests pin parity; runtime load of search-index for the filter is nicer for “reuse Ctrl+K index” wording but not mandatory if parity is tested.

**Assumption for approval:** prefer **build-time parity + filter on tree leaves** for fewer network loads on Raw, plus a pytest that search-index document set ≡ tree leaves (ids/titles/hrefs). Optionally still allow filter to use `__llmwikiLoadIndex` later without a third file.

### 2.7 Docs / changelog

- `CHANGELOG.md` `[Unreleased]`
- `docs/reference/ui.md` — Raw Documents sidebar, unified reader, filter behavior
- `docs/reference/reader-api.md` — document entry shape; tree leaf fields; note part stubs
- `docs/architecture.md` — one reader page per logical document (not per chunk file)
- Touch `cli.md` / `mcp.md` only if `--project` grouping caveat needs a one-liner pointing at site behavior

### 2.8 Files touched (expected)

| Path | Responsibility |
|---|---|
| `llmwiki/raw_docs_site.py` | Logical grouping, tree serialization, unified + stub pages |
| `llmwiki/build.py` | Wire grouping into search-index + build_site |
| `llmwiki/render/js.py` | Sidebar filter, ancestor retention, highlight |
| `llmwiki/render/css.py` | Filter input + mark styles |
| `tests/test_raw_docs_site.py` (+ new focused tests) | Grouping, tree/index parity, stubs, filter if JS-tested |
| `tests/test_248_palette_match.py` or sibling | Document entries are logical, not per-chunk |
| Docs + CHANGELOG | As above |
| `context/spec/304-unified-document-pages/*` | This AWOS package |

No new runtime Python dependencies.

---

## 3. Impact and Risk Analysis

### System Dependencies

- Static site build path only; MCP/`wiki_search` unchanged unless they consume site document URLs (provenance already uses `documents/…` paths — stubs preserve those paths).
- Demo refresh / document counts: Recent already uses grouping; after fix, `--project` demos may show **more** Recent rows (correct).

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `--project` folders mis-grouped by old heuristic | New base-slug grouping; fixtures with two docs in one project folder |
| Canonical URL collides with a part filename | Unified page uses base slug; parts keep `-NN`; stub only on `-NN` paths |
| `file://` stub navigation fails | meta refresh + visible link + relative hrefs |
| Search index key-set / size guards | Keep document entries in eager meta; body cap unchanged order-of-magnitude; update frozen-key tests if any |
| Double catalog drift | Single grouping function; parity test tree ↔ search-index documents |
| Large assembled HTML | Same content as sum of parts; no new storage rewrite |

---

## 4. Testing Strategy

- **Unit:** base-slug grouping (single file, multi-chunk default layout, two docs under one `--project` folder, clean titles).
- **Build integration:** vault fixture → `build` → one canonical HTML contains all part text; part URL is stub pointing at `#` anchor; search-index has one `type:document` per logical doc; tree leaves match index ids/titles/hrefs.
- **JS:** filter ordering (starts-with before contains); ancestor folders retained; highlight present; empty copy exact; `file://`-safe relative links (existing load patterns).
- **Acceptance:** map to functional-spec checkboxes; cover single-file + multi-chunk + shared project folder.
- **Manual smoke:** worktree vault + operator live-vault paste commands per delivery-flow (agent does not mutate live vault).

---

## 5. Assumptions to confirm

1. **Canonical URL** = `documents/<dir>/<base-slug>.html` with part stubs at `-NN` paths.
2. **Filter runs on tree leaves** that were built from the shared logical-document model; parity with search-index enforced by tests (runtime `__llmwikiLoadIndex` for filter optional, not required for v1).
3. **Part pages become stubs**, not full duplicate articles.
4. **No kind-filter chips** in this ticket.
