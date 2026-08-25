# Fix log — #140 archive/ is treated three different ways by reindex, lint and graph

Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/140

## Stage: fetch-bug + resume-detection

Issue open, no comments, no prior branch or flow log. Fresh start.

## Stage: diagnose

Reproduced all claims on `origin/main` (0f2b710) against a throwaway vault
(`init` → seed candidate → `candidates.discard()` → `reindex_wiki()` → `lint`):

- `reindex` wrote `## Archive (1)` into `index.md`.
- `lint` reported `[error] index_sync | dead index link → archive/…/Hetzner.md`
  for the link reindex had just written.
- `lint --fail-on-errors` exits 1; `.github/workflows/wiki-checks.yml:60` runs it.
- After `rm -rf wiki/archive`, reindex left the `## Archive` heading intact as
  unmanaged free text and lint still errored — consequence 3 confirmed.

Live-vault measurement (read-only, 699 live pages / 15 archived): all 15 lint
errors are this bug; 68 wikilinks across 15 slugs point at archive-only pages
and lint *already* reports them broken, because `load_pages` already skips
`archive/`. The comment at `lint/__init__.py:111` is therefore inverted.

Root cause: each component derives its own page set by `rglob` with its own
exclusion rule. Five components, three behaviours:

| Component | Rule | Treatment |
| --- | --- | --- |
| `lint/__init__.py:112` | `rel_path.parts[0] == "archive"` | excluded |
| `backlinks.py:88,206` | `"archive" in p.parts` | excluded |
| `tags.py:91` | `"archive" not in p.parts` | excluded |
| `reindex.py` | none | catalogued |
| `graph.py:188` | none | included as nodes |

Only writer into `wiki/archive/` is `_archive_candidate` (`candidates.py:979`),
reached from `discard()` (`:912`) and `merge()` (`:892`). The `ARCHIVED`
lifecycle state (`lifecycle.py`) is a frontmatter value and never moves files,
so `archive/` is strictly the candidate-triage reject bin.

## Stage: classify

**Verdict: no owning spec.** No `context/spec/*/functional-spec.md` defines
`archive/` behaviour (grep hits are unrelated review prose). The only written
intent is `CLAUDE.md`: "archive/ — Deprecated / demoted pages preserved for
history". No spec amendment; proceed without one.

## Decisions (user, this run)

1. **Cold storage.** `reindex` stops cataloguing `archive/` and prunes the
   leftover section; `graph` stops emitting archived nodes; `lint` keeps its
   skip and gets its inverted comment corrected. Aligns reindex+graph with the
   three components that already exclude it.
2. **The 68 dangling wikilinks stay, no follow-up issue.** A link to a
   deliberately discarded page reading as broken is intended behaviour.

Next stage: fix.

## Stage: fix

Single shared predicate in `llmwiki/_system_pages.py` — the module that already
owns this drift class for system pages — plus five call sites routed through it:

- `_system_pages.py` — `ARCHIVE_FOLDER` + `is_archived_path(rel_parts)`,
  top-level-only. A nested `archive/` folder stays a live page: source pages are
  grouped by project slug, so matching at any depth would silently drop every
  page under a project named `archive` from lint, graph, backlinks, tags and the
  index. A knowledge base must not lose pages without an error.
- `graph.py` — `scan_pages` skips archived pages before the `pages` dict write.
- `reindex.py` — `_discover_pages` skips the top-level `archive/` child;
  `ARCHIVE_FOLDER` added to `ALWAYS_MANAGED_FOLDERS`; a bullet whose href
  resolves into `archive/` is classified `dead` before the stray check.
- `lint/__init__.py` — skip routed through the predicate; the inverted comment
  replaced with what actually happens.
- `backlinks.py` (2 sites), `tags.py` — ad-hoc `"archive" in p.parts` replaced
  with the predicate on wiki-relative parts. Deliberate narrowing to top-level.

`ALWAYS_MANAGED_FOLDERS` alone did **not** prune the stale section, contrary to
the initial plan. `plan_reindex` keeps a bullet whose target is missing from the
page set but still present on disk (the `strays` branch, which exists to keep
hand-placed system pages listed). `discard()` leaves the file on disk, so the
bullets were re-added and the section never emptied. Both parts are required:
the `dead` classification empties the section, `ALWAYS_MANAGED_FOLDERS` makes
the emptied section droppable.

## Stage: regression-test

`tests/test_archive_cold_storage.py`, 4 tests: predicate semantics (incl.
`("sources", "archive", "x.md")` is not archived), end-to-end
discard → reindex → no `## Archive` and zero `index_sync` findings, stale
section pruned from an existing index, archived pages absent from graph nodes.
3 of 4 fail on pre-fix code with the source change stashed.

## Stage: verify-criteria

No spec acceptance criteria to re-check (no owning spec). Verified against a
copy of the real vault (live vault never mutated), same copy both sides:

- pre-fix: 1129 errors = 1114 `provenance_integrity` + 15 `index_sync`
- post-fix: 1114 errors, `index_sync` section absent
- `link_integrity` 811 and `contradiction_detection` 26 identical both sides —
  the dangling links to discarded slugs stay broken, per decision 2
- `index.md` 720 → 703 lines, the `## Archive` block and nothing else
- graph nodes 700 → 685

(The `provenance_integrity` count is an artifact of copying `wiki/` without
`raw/`; it is identical on both sides and unrelated to this change.)

Gates: `ruff check llmwiki tests scripts` clean; `pytest tests/ -q`
4072 passed, 48 skipped, 0 failed. Smoke confirmed by the user.

Next stage: local review, then commit-push.

## Stage: local-review

One independent reviewer, fixed prompt, no run-time focus areas. Verdict
**Approve**, 0 blockers, 6 nits — `context/fix-log-140-review.md`. All six kept.
Nit 2 applied as documentation only; the preamble-carrying variant was declined
as out of scope.

## Stage: scope extension (user decision, after review)

Review nit 3 surfaced four more wiki-wide scanners. The user's rule for them:
dismissing a candidate means "this term is noise — a service command name, an
example, something repeated by accident" — in practice agent tool names and
generic terms a synthesis pass wikilinked. Nothing that reads *content* may
surface an archived page. Confirmed by live call that `tool_wiki_search` returned an
archived page, and `CONTENT_ROOT = resolve_content_root()` resolves to the
user's real vault.

Routed through `is_archived_path`: `mcp/server.py` `_iter_scan_files`
(per-root, so a `raw/sessions/archive/` folder is still scanned), `tool_wiki_query`,
`tool_wiki_lint`, and `graphify_bridge._extract_wiki_nodes`. `tool_wiki_lint` and
`llmwiki lint` now agree that a link to a discarded slug is broken.

`candidates_harvest.py:75` deliberately unchanged (comment only). Its `resolved`
set includes `archive/`, which is the only record that a term was dismissed:
routing it through the predicate would re-propose every dismissed term on the
next `synth` and every one after. `archive/` therefore has two roles — cold
storage for content readers, authoritative dismissal ledger for harvest. A test
locks the second one; verified load-bearing by temporarily adding the filter and
watching the dismissed term come back.

Decision 2 reaffirmed: dangling `[[wikilinks]]` stay broken, no follow-up issue,
no page bodies rewritten.

Independently verified after the change: MCP search archive hits 1 → 0 while a
`raw/sessions/archive/` page still matches; a dismissed slug not re-harvested
after discard; `candidates_harvest.py` byte-identical to `origin/main` apart from the
comment. Gates: `ruff` clean, `pytest` 4079 passed / 48 skipped / exit 0.

Next stage: commit-push, then PR. This is the flow log's last committed entry —
later stages are reported in chat and via §9 exceptions only.
