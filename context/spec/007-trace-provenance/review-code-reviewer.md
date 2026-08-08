# Code review — 007 trace provenance (#122)

**Reviewer:** code-reviewer subagent
**Scope:** `git diff origin/main...HEAD` (committed: `context/spec/007-trace-provenance/*` only) plus all uncommitted worktree changes on `feat/122-trace-provenance` — `llmwiki/trace.py`, `llmwiki/lint/rules/provenance_integrity.py`, `llmwiki/build.py`, `llmwiki/candidates.py`, `llmwiki/cli.py`, `llmwiki/raw_docs_site.py`, `llmwiki/state_store.py`, `llmwiki/topics_page.py`, related tests (including untracked `tests/test_trace.py`, `tests/test_cli_trace.py`, `tests/test_provenance_sources_links.py`, `tests/test_source_file_index.py`, `tests/test_122_acceptance.py`), docs, CHANGELOG, `context/`.
**Verdict:** **Request changes** — 1 critical, 3 important.

## Gate status

| Gate | Result |
|---|---|
| `ruff check` (touched Python) | pass |
| Focused pytest (`test_trace`, `test_cli_trace`, `test_provenance_sources_links`, `test_source_file_index`, `test_122_acceptance`, one lint rule case) | pass |
| CHANGELOG under `## [Unreleased]` | present (`### Added` #122; also `### Fixed` #81 backfill — see I2) |
| Docs for user-visible change | `docs/reference/cli.md` (`## trace`, Rules), `docs/UPGRADING.md`, `docs/reference/ui.md` |
| AWOS `context/` touched (CONTRIBUTING #13) | yes |
| New runtime deps | none |
| One concern per PR | **no** — #122 + #81 Home `on_disk` backfill mixed (see I2) |

## Critical

### C1. Document Sources prefer-HTML hrefs disagree with where `build` writes document pages (confidence 92)

`llmwiki/trace.py` `_site_href_for_wiki_page` reuses `llmwiki.graph._compute_site_url` for FR2 “prefer compiled HTML”. For flat `source_file: raw/docs/<stem>.md` (no `/` after `raw/docs/`), `_compute_site_url` returns `documents/<project>/<stem>.html` when frontmatter `project:` is set (`llmwiki/graph.py` ~119–123). The actual document renderer writes `documents/<rel>.html` with `rel` relative to `raw/docs/` — so a flat file is **`documents/<stem>.html`**, not under a project segment (`llmwiki/raw_docs_site.py` `File.out_rel`).

Reproduced on this branch:

- Actual site file: `site/documents/note.html`
- Computed href: `documents/myproj/note.html`
- With only the real file present, `_verify_site_url` clears the href; `raw_site_copy_href` returns `None` for all `raw/docs/**` (`llmwiki/trace.py` ~339–355), so `sources_links` **omits** the Sources entry entirely — FR2 “every Sources entry is a working link” fails by silence.
- If a prior/wrong tree happens to create `documents/myproj/note.html`, `sources_links` emits a **404** prefer-HTML link while the live page is at `documents/note.html`.

Session `raw/sessions/` layout is tested and correct; acceptance/`test_provenance_sources_links.py` never cover document sources. Nested `raw/docs/<dir>/<file>.md` paths coincidentally match (`documents/<dir>/<file>.html`).

**Fix:** Resolve document site hrefs from the same rule as `File.out_rel` (`documents/` + path under `raw/docs/` with `.html`), not `documents/{project}/{stem}` for flat files. Add a unit/build test that a wiki source with `source_file: raw/docs/note.md` links to `documents/note.html` when that file exists under `site/`. Do not rely on graph’s flat-doc branch until it matches the renderer.

## Important

### I1. Document pages drop primary provenance when `exclude_href` matches (no raw fallback) (confidence 90)

`provenance_links_for_raw` deliberately clears the wiki-summary HTML when it equals `exclude_href` (the page being rendered), then falls back via `raw_site_copy_href`. That fallback only maps `raw/sessions/…` → `sources/…` and returns `None` for documents.

Verified: nested `raw/docs/proj/note.md` with `site/documents/proj/note.html` present yields a prefer-HTML link; with `exclude_href='documents/proj/note.html'` the result is **`[]`**. Session pages under the same exclude pattern correctly keep a `(raw)` `target="_blank"` link (`test_provenance_links_for_raw_excludes_self_html`).

FR2 AC for session/document pages requires prefer-HTML-else-raw(new-tab). Document HTML therefore ships with an empty Sources block for the common “this page is the compiled form of its own wiki summary” case unless nested `sources:` add other hops.

**Fix:** When HTML is excluded/missing for a document raw path, emit a raw/new-tab href that actually exists in the built site (e.g. a known documents-tree / download path the static site already serves), or document that document pages only show *further* Sources and adjust FR2/tests accordingly — but do not claim FR2 parity with sessions while `raw_site_copy_href` returns `None` for all docs.

### I2. CONTRIBUTING “one concern per PR” — #81 Home `on_disk` backfill rides with #122 (confidence 95)

Uncommitted changes include `pipeline_rows_missing_on_disk` / `_ensure_synth_pipeline_snapshot` refresh behaviour, CHANGELOG `### Fixed` bullet for “Home On disk column stuck at 0”, `tests/test_state_widget.py` backfill coverage, and `context/spec/006-honest-synthesized-counts/flow-log.md` follow-up notes — alongside the #122 walker/CLI/lint/site work.

CONTRIBUTING TL;DR #1: one concern per PR. A reader of #122 cannot review provenance without also absorbing a Home-widget state migration. Split into a `fix:` PR for #81 (or land it alone) and keep #122 to trace/lint/Sources.

### I3. Absolute local worktree path in git-bound flow log (confidence 88)

`context/spec/007-trace-provenance/flow-log.md` (committed + WT) records:

`WT=.claude/worktrees path (redacted)/.claude/worktrees/feat-122-trace-provenance`

CONTRIBUTING privacy / `.cursor/rules/no-local-vault-in-prs`: absolute home paths must not appear in PRs, commits, or CHANGELOG. Spec `context/` in this repo is intended to ship with the PR (CI #13). Replace with placeholders (`$WT`, `<worktree>`, relative path from repo root).

## Non-blocking notes (below the report threshold)

- Slice 4 checkbox text in `tasks.md` still describes frontmatter provenance panels on topic pages; revised FR2 + code use graph evidence under a collapsible Sources section — update the task wording so the `[x]` matches behaviour.
- `_SOURCE_FILE_INDEX_CACHE` never invalidates for the process lifetime when callers omit `index=`; fine for one-shot `build` (explicit index), risky for long-lived watch/MCP if wiki sources change mid-process.
- `resolve_source_page` still allows `sources / f"{slug}.md"` path segments; `trace_page` mitigates with `_under_vault`, but slash-bearing slugs remain footguns.
- Implementation is largely uncommitted; conventional-commit titles / PR checklist evidence cannot be fully reviewed until commits exist.
