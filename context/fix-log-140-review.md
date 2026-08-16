# Local review — #140 `wiki/archive/` is cold storage

**Scope reviewed:** working-tree diff on `fix/140-archive-cold-storage` (branch is level with `origin/main` @ `0f2b710`; all changes are uncommitted, so `git diff` + untracked files were reviewed, not `origin/main...HEAD`).

Files: `llmwiki/_system_pages.py`, `llmwiki/backlinks.py`, `llmwiki/graph.py`, `llmwiki/lint/__init__.py`, `llmwiki/reindex.py`, `llmwiki/tags.py`, `CHANGELOG.md`, `CLAUDE.md`, `docs/UPGRADING.md`, plus untracked `tests/test_archive_cold_storage.py` and `context/fix-log-140.md`.

## Verdict

**Approve** — no blockers. Six nits, none of which need to hold the push; #1, #3 and #6 are the ones worth doing before commit.

| Severity | Count |
| --- | --- |
| Blocker | 0 |
| Nit | 6 |

## What was verified

- `python3 -m pytest tests/ -q` — full suite green on the branch (no failures, no errors).
- `ruff check .` — clean.
- **Regression tests genuinely regress.** Copied `origin/main` into a throwaway tree, dropped in `tests/test_archive_cold_storage.py` with the predicate inlined (it does not exist on main), and ran it: all three behavioural tests fail on main (`## Archive` written into `index.md`, stale section survives, `Bogus` present in `scan_pages`) and pass on the branch. This satisfies the checklist's "Regression tests lock in recent fixes".
- **Build + runtime smoke.** `python3 -m llmwiki build --vault <copy of demo> --out <tmp>` — exit 0, 289 HTML files, no network lines, no new warnings. Repeated with a planted `wiki/archive/candidates/…/ZzTestDiscarded.md` in the vault copy: zero occurrences of the slug anywhere under the built site, so cold storage does not leak into `site/`.
- **The fix is internally coherent with `index_sync`.** `lint/rules/index_sync.py` resolves index hrefs against `load_pages()`, which already skipped `archive/`; so any surviving `archive/…` bullet is by construction a `dead index link`. Routing those bullets into `dead` in `plan_reindex` (rather than `strays`, which keeps a bullet alive whenever the file is still on disk) is the correct branch — the `strays` path was the actual reason `ALWAYS_MANAGED_FOLDERS` alone would not have emptied the section.
- **Security + privacy (checklist § Security + privacy):** nothing renders new frontmatter or body content into HTML, no new server code, no new runtime deps (stdlib only — `PurePosixPath` import), no network, no telemetry. CI's privacy grep target (`deepshikhasingh`) does not appear in the diff. `context/fix-log-140.md` carries aggregate vault counts only — no slugs, titles, home paths or usernames — so it stays inside CONTRIBUTING § 260.
- **Meta (checklist § Meta):** one concern, CHANGELOG entry under `## [Unreleased]`, tests added, AWOS context satisfied via `context/fix-log-140.md` (`llmwiki/` + `tests/` touched → `context/` change required; remember to `git add` it — it is untracked). Conventional-commit title and issue link in the PR body cannot be checked yet because nothing is committed; use a `fix:` title referencing #140.

## Blockers

None.

## Nits

### 1. The folder name is now defined twice — same drift class the change removes

`llmwiki/candidates.py:53` still declares `ARCHIVE_DIR_NAME = "archive"`, and `archive_dir()` (`:148`) builds the destination from it. `_system_pages.ARCHIVE_FOLDER` is the new authority for *reading* cold storage; `candidates.py` is its only *writer*. Two independent string constants for one folder is precisely the drift the module docstring says this consolidation exists to end — rename the writer's folder and five readers silently stop recognising it.

Checklist: § Code quality ("No dead code" / duplication), and the stated intent of `_system_pages.py`.

Fix: in `llmwiki/candidates.py`, replace the literal with the shared constant —

```python
from llmwiki._system_pages import ARCHIVE_FOLDER

ARCHIVE_DIR_NAME = ARCHIVE_FOLDER
```

keeping the local alias so the rest of the module is untouched.

### 2. Reindex now silently deletes hand-written prose under `## Archive`

Adding `archive` to `ALWAYS_MANAGED_FOLDERS` makes `## Archive` a *managed* section whose bullet list is always empty, so `_render` drops the whole block (`reindex.py:485`, "Drop empty non-canonical sections") — including any non-bullet text `plan_reindex` collected into `section_preambles["archive"]`. Verified: an index containing

```markdown
## Archive (1)

Note: I keep discarded stubs here on purpose, do not delete.

- [Bogus](archive/candidates/t/Bogus.md)
```

comes back from `reindex_wiki()` with the heading, the bullet **and the note** gone. That contradicts the module docstring's own promise — "deliberately conservative about text it did not write" / "Unmanaged sections and free text are left alone" — and it is silent (the note is not reported in `plan.removed`).

Checklist: § Docs ("docstrings match the code") and § Code quality.

Fix: cheapest is honest documentation — add one line to the `docs/UPGRADING.md` #140 section: "Any note you hand-wrote under `## Archive` is removed along with the heading; move it above the first section first." The thorough version is to carry non-placeholder `section_preambles[ARCHIVE_FOLDER]` lines into the preceding unmanaged chunk instead of discarding them.

### 3. `CLAUDE.md` / `CHANGELOG.md` claim more coverage than the code has

The new `CLAUDE.md` text says archived pages are "never catalogued in index.md, linted, graphed, or tagged". Three more wiki-wide scanners still walk `archive/`:

- `llmwiki/mcp/server.py:983` — the MCP link-integrity scan builds `pages[slug]` from a bare `wiki.rglob("*.md")`, so it *resolves* `[[wikilinks]]` against discarded slugs. That is the exact opposite of the decision recorded in this change ("a link to a discarded page reads as broken on purpose"), so `llmwiki lint` and the MCP tool now disagree about the same vault.
- `llmwiki/mcp/server.py:617` — `wiki_query` can quote a discarded page back to the user.
- `llmwiki/graphify_bridge.py:85` — emits archived pages as graph nodes, contradicting `graph.scan_pages`.
- `llmwiki/candidates_harvest.py:75` — the `resolved` slug set includes `archive/**`, so a discarded candidate is treated as already-existing and is never re-harvested. That may well be *desirable*, but right now it is an accident of `rglob`, not a stated rule.

All four are pre-existing and out of the five components the CHANGELOG names — the CHANGELOG sentence "cold storage in all five" is accurate as written. The `CLAUDE.md` sentence is not, because it reads as a global invariant.

Checklist: § Docs ("docstrings match the code").

Fix: either route those four through `is_archived_path` in this PR (it is a two-line change each), or soften `CLAUDE.md` to name the surfaces that honour it ("not catalogued in `index.md`, not linted by `llmwiki lint`, not a graph node, not tagged") and file a follow-up issue for the MCP/graphify/harvest scanners.

### 4. `docs/roadmap.md:134` still plans to put live pages in the reject bin

Roadmap row `S-L1-04` is "`/wiki-archive` — move stale entries to `wiki/archive/`". Under the new rule, anything that command moves would vanish from the index, the graph, the tag index, backlinks and lint **without an error** — the exact silent-loss failure mode `is_archived_path`'s docstring argues against. The decision recorded here needs to reach that row, or the future command needs a different destination.

Checklist: § Docs ("docs/ updated for any architectural change").

Fix: annotate the roadmap row, e.g. `| S | L1 | S-L1-04 | \`/wiki-archive\` — move stale entries to a *live* folder; \`wiki/archive/\` is cold storage since #140 | |`.

### 5. The narrowing from any-depth to top-level is untested for `backlinks` and `tags`

`backlinks.py:89,207` and `tags.py:95` changed from `"archive" in p.parts` to a top-level-only predicate. That is a real behaviour change for both modules — `wiki/sources/archive/x.md` now *gets* a backlinks block and *does* contribute to the tag index. `test_archive_cold_storage.py` pins the predicate in isolation and pins reindex, lint and graph end-to-end, but nothing exercises backlinks or tags at all, so a future revert to `in p.parts` would stay green.

Checklist: § Tests ("cover the happy path AND at least one edge case").

Fix: add one test that writes `wiki/sources/archive/x.md` plus `wiki/archive/candidates/t/Bogus.md`, then asserts `backlinks._collect_pages` (or `prune_all`) and `tags._iter_wiki_pages` include the former and exclude the latter.

### 6. `docs/UPGRADING.md` now has two adjacent, partly contradictory `## Unreleased` archive sections

The new "`wiki/archive/` is cold storage everywhere (#140)" block at `:106` sits directly above the older "lint skips `wiki/archive/`" block at `:114`. A user upgrading reads the narrow, superseded statement second and cannot tell which is current.

Checklist: § Docs.

Fix: fold the older block's one bullet into the #140 section and delete the duplicate heading.

## Notes, not findings

- `_system_pages.py`'s new comment opens with what the code *used to* do. That is normally worth flagging, but it matches the established `#arch-l7` note directly above it in the same file, so it reads as house style here.
- `is_archived_path` is case-sensitive, so a hand-created `wiki/Archive/` on a case-insensitive filesystem would be catalogued. Every neighbouring folder check in `reindex.py` behaves the same way; not worth diverging for.
