# Design: document-centric static site (Home file tree, Analytics, Recent)

Date: 2026-07-03
Status: approved

## Goal

Restructure the generated static site around the user's raw documents
(wiki-add docs), not around project analytics:

- `index.html` (Home) becomes a file-tree browser of `raw/docs/**`.
- The current Home content (hero stats, heatmap, token stats,
  recently-updated, projects grid) moves to a new `analytics.html`.
- `changelog.html` is removed; a new `recent.html` lists the newest raw
  documents and sits right after Home in the nav.

## Background

`raw/` holds two kinds of content: Claude Code session transcripts (flat
files in `raw/sessions/`) and wiki-add documents (`tags: [wiki-add,
raw-doc]`). kbbuilder's `makeRawDocWriter` historically wrote docs into
`raw/sessions/<slug>/` subfolders because `raw/docs/` had no synthesis
consumer (llm-wiki #1). That is fixed — `_discover_raw_docs` is wired into
`llmwiki/synth/pipeline.py` — so the workaround is obsolete.

## Decisions (locked with user)

1. **Tree scope**: `raw/docs/**` only, after a one-time relocation of the
   misplaced doc folders out of `raw/sessions/`.
2. **Recent page**: raw documents only, newest first, one row per document
   (chunk files `-NN` collapse into their parent doc).
3. **Tree UX**: static page per document with a shared left-side file-tree
   sidebar; current doc highlighted. Home = tree + intro pane.
4. **Nav order**: Home · Recent · Graph · Projects · Sessions · Analytics ·
   Docs. Applied to top nav, mobile drawer, and mobile bottom nav.
5. **Changelog**: removed from the site entirely (lives on GitHub).

## Changes

### A. Data layout (vault, one-time)

- Move `raw/sessions/{openclaw-vps-infrastructure,evrika-1,document}/` →
  `raw/docs/…` (content untouched).
- Rewrite the affected rel-paths in the synthesis state so already-processed
  docs are not re-synthesized as duplicates.

### B. kbbuilder (separate repo/commit)

- `src/wiki-worker.ts` `makeRawDocWriter`: write to `raw/docs/<slug>/`
  instead of `raw/sessions/<slug>/`; update stale comment and tests.

### C. llm-wiki site generator

- New module `llmwiki/raw_docs_site.py`:
  - scan `raw/docs/**/*.md`, parse frontmatter, group multi-chunk docs by
    parent folder;
  - build the tree model and render: sidebar HTML (shared), per-doc pages
    under `site/documents/…`, Home tree pane, Recent list.
- `llmwiki/build.py`:
  - nav order change (top nav, drawer, mobile bottom nav);
  - `index.html` renders the tree browser;
  - `analytics.html` renders the old Home body;
  - `recent.html` renders the recent-documents list;
  - remove `render_changelog()` and all changelog references;
  - add document pages to `search-index.json`, sitemap, llms.txt.

### D. Testing

- Unit tests: tree builder (grouping, chunk collapsing, ordering), recent
  list (date sort, one-row-per-doc), nav contents, changelog absence.
- Full suite via `env -u LLMWIKI_ROOT python3 -m pytest`.
- Manual: `llmwiki build` against the real vault; inspect Home, a chunked
  doc page, Recent, Analytics.
