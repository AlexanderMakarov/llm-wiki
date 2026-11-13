# Flow log — #277 remove dangling sources/wikilinks

## fetch-bug
- BUG_ID: 277
- Title: remove leaves dangling sources: entries and wikilinks, failing lint --lint-fail errors
- Labels: bug, self-heal
- Symptom: `llmwiki remove` deletes wiki/sources pages + synth/catalog state but leaves removed slugs in entity/concept/project `sources:` frontmatter and `[[slug]]` wikilinks; next lint provenance_integrity errors fail automation
- Expected: prune removed slugs from citing pages' `sources:`; drop list-only wikilinks / delink embedded; report in remove summary/dry-run/log
- Issue notes: do not use wiki-wide `backlinks.prune_all`; targeted per-slug rewrite in remove path
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/277
- Next: resume-detection

## resume-detection
- Issue OPEN; no merged PR for #277 (search hit unrelated #300)
- No pre-existing owning functional-spec for remove back-ref pruning; allocate orphan fix-as-spec `277-remove-dangling-refs`
- SPEC_NAME: `277-remove-dangling-refs`
- Next: workspace

## workspace
- BRANCH: `fix/277-remove-dangling-refs`
- WT: `.claude/worktrees/fix-277-remove-dangling-refs`
- TMP_VAULT: `.worktree-vault` (isolated config.json)
- MAIN: `<repo>`
- Base: origin/main @ f20710a
- Next: diagnose

## diagnose
- Repro: PASS on TMP_VAULT — after remove, lint provenance_integrity reported missing source summary for citing entity/concept pages; dangling sources: + [[wikilinks]] remained
- Root cause: `llmwiki/remove_doc.py:execute_remove_plan` deletes raw/source/synth then only `_rebuild_index` + `_append_log`; no citing-page rewrite. Plan text falsely says "prune backlinks"
- Helpers: `candidates.rewrite_links_in_wiki` (per-slug → None = plain text); promote `migrate_broken_provenance._rewrite_sources_line`; `parse_sources_field`
- Proposed shape: plan collects removed_slugs + citing pages; execute trims sources: then rewrite_links_in_wiki; report counts in dry-run/summary/log; never prune_all
- Next: classify

## classify
- Verdict: orphan incomplete product behavior — no pre-existing functional-spec to amend; skip amend-spec
- SPEC_NAME: `277-remove-dangling-refs`
- Operator decisions: (1b) auto-archive page when `sources:` becomes empty after prune; (2a) delink/trim only, no Contradictions/review notes; (3a) drop list items that are only a wikilink to a removed slug; (4a) wiki-wide rewrite except archive/ and pages being deleted
- Next: fix

## fix
- `llmwiki/remove_doc.py`: `build_remove_plan` now fills `removed_slugs` (stems of planned source pages minus stems a surviving source page still carries), `delink_keys` (removed-slug `norm_page_key`s no surviving page answers to by stem or `## Aliases`) and `citing_pages` (`PageEdit` per live page outside `wiki/archive/` and `log.md`). `execute_remove_plan` applies the same `_edit_page` pass after unlinking source pages and before `_rebuild_index`: list items that are only a wikilink to a removed slug are dropped, other wikilinks become plain text, `sources:` is trimmed, and a curated page (`entities/ concepts/ projects/ syntheses/ candidates/`) left with no `sources:` moves to `wiki/archive/<rel>` (UTC-stamp folder on collision) with inbound links delinked. `backlinks.prune_all` is never called. (Local-review N1 later added a dismissal-ledger write for archived pages; see `## local-review`.)
- `candidates.rewrite_sources_line` is the promoted public form of `migrate_broken_provenance._rewrite_sources_line` (private copy removed).
- `format_plan`, the CLI summary and the `remove` log entry report citing pages, sources trimmed, links unlinked, list items dropped and pages archived; the false "prune backlinks" wording is gone from `format_plan`, the `remove` docstring, `--help` and `docs/reference/cli.md`.
- Deviations from the operator brief: wikilinks are kept when another live page still answers to the name (e.g. a project page named like the source slug), and the append-only `log.md` is not rewritten.
- Tests: extended `tests/test_remove_doc.py` (provenance lint clean, unrelated untouched, dry-run writes nothing, empty-sources archive + collision, link-only bullets, prose delink, system pages never archived, shared stem, CLI summary + log).
- Risk (resolved in local-review N1): an archived page's name is settled for harvest; now persisted in the dismissal ledger instead of relying on archive layout.
- `llmwiki/doctor/heal_kb.json`: no change (no error string touched).
- Next: regression-test

## regression-test
- Extended `tests/test_remove_doc.py` (23 passed); RED confirmed by temporarily disabling cleanup (7 new tests fail)
- Orchestrator re-ran `pytest tests/test_remove_doc.py -q` → 23 passed; ruff clean on touched files
- Next: verify-criteria

## verify-criteria
- TMP_VAULT e2e: dry-run listed citing pages + Solo will-archive; execute cleaned 2 citing pages / archived Solo; `lint --rules provenance_integrity` → 0 issues; Acme kept `sources: [keep-me]`, list-only `[[old-project]]` dropped, prose delinked
- Live smoke (operator-approved): removed `<live-doc-slug>/…` from the live vault; cleaned one `<entity>` page (1 source trimmed, 1 list item dropped); lint provenance_integrity still 0 issues; backup at `<tmp>/llmwiki-277-smoke-backup-<stamp>`
- Smoke confirm: operator confirmed live remove + rebuild works
- Next: amend-spec

## amend-spec
- Skipped — orphan fix-as-spec; no pre-existing functional-spec to amend
- Next: local-review

## local-review
- Review file: `context/spec/277-remove-dangling-refs/review.md` (session-only, not staged)
- Verdict: Request changes — Blockers 2, Nits 3
- Operator keep/drop: **keep all**
- Operator notes: B1 keep log append-only; N1 remove must mark topic "don't add as candidate again" in persistence + CLI description
- Next: apply findings (below) then static gate

## local-review (post-apply)
- B1 fixed: the inbound delink after archiving now walks `_live_pages` (skips `wiki/archive/` and `is_log_page`), so `log.md` and `log-archive-*.md` are never rewritten and `links_unlinked` counts live-page links only. Regression test archives a page while the log and a log archive contain `[[Bar]]`.
- B2 fixed: this flow-log scrubbed of home paths, usernames, live-vault slugs, entity names and tmp backup paths (placeholders `<repo>`, `<live-doc-slug>`, `<entity>`, `<tmp>`). `review.md` stays unstaged.
- N1 fixed (design): `remove` upserts a dismissal (`archived by remove: last citing source removed`) into `wiki/archive/candidates/dismissals.json` for every curated page it archives (filename stem and, when different, frontmatter `title`); `stub` is the archived file relative to `wiki/archive/candidates/`. `harvest_targets` adds ledger dismissal keys to its resolved set. Documented in `docs/reference/cli.md` and the CHANGELOG entry.
- N2 fixed (docs): `docs/reference/cli.md` notes that unlinking is not fence-aware while list-item dropping is.
- N3: flow-log is the only `context/` file for this orphan fix-as-spec; stage it (not `review.md`) at commit.
- Tests: `tests/test_remove_doc.py` (log append-only, ledger rows, no record without archive, harvest not re-opening) and `tests/test_candidates_harvest.py` (ledger-only dismissal); harvest tests confirmed RED with the resolved-set change disabled.
- Static gate: `ruff check llmwiki tests scripts` clean; `pytest tests/ -q` exit 0
- Next: commit-push

## commit-push
- Issue link keyword for PR: `Closes #277` — issue acceptance delivered (prune sources:/wikilinks, report in summary/dry-run/log, archive empty-sources pages, persist settled names)
- Stage product files + this flow-log; exclude `review.md`, vault/config, `.worktree-vault/`
- Next: remote-gates (stop appending this tracked log once the PR is open)

## local-review-2 (post-apply)
- Review file: `context/spec/277-remove-dangling-refs/review.md` (session-only, not staged). Verdict: Comment — Nits 6, operator keep/drop: **keep all**. Applied uncommitted in the worktree.
- N1: `dismissal_ledger.build_ledger_from_archive` now also walks the rest of `wiki/archive/` after `archive/candidates/` and records the filename stem and a differing frontmatter `title` of each page under `REMOVE_DISMISSAL_REASON` with `stub` relative to `archive/candidates/` (`../entities/Foo.md`); candidate rows (including empty reasons) are unchanged and win key collisions. `load_ledger` auto-rebuilds whenever `wiki/archive/` exists (not only `archive/candidates/`). Docs: `cli.md` (`remove`, `migrate dismissal-ledger`), `--help`, module docstrings.
- N2: `execute_remove_plan` preflights the ledger (`_preflight_ledger`) before the first deletion when a page is due for archiving; a corrupt `dismissals.json` raises `RemoveIncompleteError` naming `migrate dismissal-ledger` (CLI exit 2, nothing removed). In the page phase the ledger row is written before the page moves, and a per-page read/write/archive `OSError` goes to `plan.page_errors` (stderr list, exit 1, `remove` log entry) while remaining pages are still cleaned.
- N3: `candidates._iter_live_markdown`, `_live_page_owners`, `_live_page_keys` and `rewrite_links_in_wiki` take an `exclude` predicate; new shared `candidates.page_names` (stem + aliases). `remove_doc` drops its own walk, owned-set copies and inbound rewrite loop and uses these (log pages and about-to-delete source pages excluded via `_skipping`). One test wrapper in `tests/test_candidates_site.py` now forwards kwargs.
- N4: `_edit_page` drops link-only list items from the body only (frontmatter via `_split_frontmatter`); wikilinks still become plain text page-wide. An emptied `## Connections` is documented as left for lint / the agent (no placeholder).
- N5: `candidates.read_page_text` / `write_page_text` (bytes, no newline translation) are used by `_apply_page_edits` and `rewrite_links_in_wiki`, so CRLF survives both the citing-page edit and the inbound delink. New `candidates.frontmatter_sources` + block-aware `rewrite_sources_line` (inline and `- slug` block lists, BOM-tolerant, requires a closed frontmatter block) are shared by `remove` and `migrate broken-provenance`.
- N6: `CLAUDE.md` / `AGENTS.md` `archive/` rows mention `remove`-archived pages (AGENTS.md had no `archive/` row; one added); `docs/reference/ui.md` and `cli.md` near-match text notes the `archived by remove: last citing source removed` rows.
- Tests: extended `tests/test_remove_doc.py` (ledger rebuild keeps remove rows + reviewer rows, rebuild without candidates dir, corrupt ledger aborts before deletes + CLI exit 2, corrupt ledger ignored when nothing archives, unwritable page reported with exit 1, frontmatter list kept, CRLF kept incl. inbound delink and archived page, block-style sources trimmed/archived, `rewrite_sources_line` forms); each new rule confirmed RED by temporarily disabling it.
- CHANGELOG #277 Fixed entry updated in place. `heal_kb.json`: no change (no existing catalog row for remove / dismissals.json).
- Deferred risk: a *candidate* archived by `remove` lands at `archive/candidates/<name>.md`, so a ledger rebuild keeps its name settled but with an empty reason.
