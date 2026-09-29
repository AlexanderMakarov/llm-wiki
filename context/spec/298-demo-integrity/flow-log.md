# Flow log: 298-demo-integrity

## fetch-bug
- BUG_ID: 298 — "Demo ships duplicate product docs: refresh_demo.py removes by path-derived directory, not by source:"
- SPEC_NAME: `298-demo-integrity` (orphan fix-as-spec, #164 — maintainer tooling and demo data; no owning functional-spec)
- Branch: `fix/298-demo-integrity`
- Entry: found during the release-day demo refresh for the next cut. The refresh needed a manual migration and hand repairs, failed five #248 tests and the #197 search baseline, and would have shipped the maintainer's home directory in demo state. Every defect below surfaced in that one refresh; this PR fixes the tooling and ships the cleaned demo.
- Related: #277 (open — `remove` leaves dangling references), #297 (filed — refresh re-synthesizes whole docs and is not restartable), #299 (filed — pre-#204 candidate siblings never refresh), #212 (Homebrew tap).

## diagnose
Five defects, each reproduced on the committed demo:

1. **Session re-date strands source pages.** A session source page's name carries the session `date` (#265). `generate_demo_sessions.py --today` moves `date` in raw frontmatter, so every derived page name moved while the committed pages kept the old name; `synth --sessions-only` then skipped all 25 as "already claimed by a real page under another name". The script's docstring claimed links "usually remain valid".
2. **Duplicate docs (#298).** 31 of 75 distinct demo docs existed under two `raw/docs/` dirs with the same `source:` — the #143 seed wrote title-derived dirs (`claude-code-adapter/`), `refresh_demo.py` writes `slug_for(path)` dirs (`adapters-claude-code/`) and removes only that one. Each refresh left the seed copy beside the re-added one, and a seed-only doc became a new duplicate the first time it changed. Two source pages per title took the search baseline from MRR 0.966 to 0.938 (titles on 2+ pages: 9 → 25).
3. **Home directory in demo state.** `refresh_demo.py` passed `llmwiki add` an absolute path; `add_pipeline` records its argument in `queue.items[].payload.sources`, so `demo/llmwiki-state.json` and its `.js` sidecar carried 34 absolute home paths. HEAD's demo queue was empty.
4. **#248 tests pinned one synthesis outcome.** `_EMPTY_ISOLATED = {"Python"}` hard-coded which curated topic the empty-page rule suppresses. That depends on which `[[links]]` synthesis writes: on this re-synth SQLite lost its three linking sources (degree 13 → 0) and Python gained one (degree 0 → 1). The rule still held; only the example flipped.
5. **Stale candidate siblings (#299).** `candidates/entities/llmwiki.md`, `llm-wiki.md` and `concepts/Wikilinks.md` fold to the same `norm_page_key` as the live `LLM Wiki.md` / `entities/wikilinks.md`. `_existing_stub` refreshes only the first match, so the siblings kept 2026-09-08 evidence, including references to pages this refresh removed. `candidates merge` cannot fix them: it refuses cross-kind targets as "into itself" and, same-kind, unions the stale `sources:` into the live stub.

Also found: `docs/deploy/homebrew-setup.md` told users to tap and clone the upstream owner's tap, and the rest of the Homebrew kit published nothing this fork owns (#212).

## classify
- 1–3: **Conformance.** The release process already promises a refresh without manual repair, a demo without duplicate content, and no personal machine details in committed files.
- 4: **Test defect.** The product rule is unchanged; the test hard-coded demo data a re-synth can change.
- 5: filed as #299; this PR only removes the three stale stubs from the demo.
- Homebrew: **Removal**, per #212's own "what must not persist" clause.

## fix
- `generate_demo_sessions.py`: a real write ends with `migrate source-page-paths` over `demo/` and exits non-zero on its errors; `--dry-run` only reports it.
- `refresh_demo.py`: `expand_removes` follows every planned `remove` with removes for other dirs holding the same `source:` (shown in `--dry-run`); `add` gets the repo-relative path, run from the repo root, so the raw `source:` is unchanged and nothing absolute is recorded.
- `test_248_acceptance.py`: `_EMPTY_ISOLATED` is read off the committed vault (co-occurrence edges plus `page_content`), with a test that it is non-empty and a proper subset so both sides of the rule stay exercised; the count assertions derive from it.
- Homebrew kit removed (formula, bump script, workflow, setup doc, tests, README and tutorial install lines, link-check placeholder, allowlist entries); #212 records the commit and lines to restore from.
- Docs: `RELEASE_PROCESS.md`, `REFRESH_DEMO.md` and the `/release` skill describe the re-home step and require explaining a search-baseline drop before re-recording it.

## regression-test
- `test_release_day_write_rehomes_source_pages` / `test_dry_run_leaves_source_pages_in_place` — RED with the generator change stashed (page stays at its old name), GREEN with it.
- `test_remove_also_takes_other_dirs_holding_the_same_source`, `test_remove_of_a_seed_only_doc_takes_its_seed_dir`, `test_add_only_plan_is_not_expanded`.
- `test_committed_demo_holds_each_product_doc_once` — RED on the pre-cleanup demo (31 shared `source:` values).
- `test_committed_demo_carries_no_real_home_directory` — RED on the refreshed demo before cleanup (state `.json` / `.js`); scans only files git would commit.
- `test_run_refresh_passes_path_scoped_synth` now also asserts `add` receives `docs/guide.md`, not an absolute path.

## demo data
- Sessions re-dated to 2026-09-28 and re-synthesized (25); 34 changed product docs refreshed. The first docs synth was interrupted when its parent session exited; the 21 missing pages were finished with a path-scoped `synth --docs-only`, `--verify-slugs` exited 0, and the pin was advanced by hand (#297).
- Removed the 31 seed copies and the Homebrew doc copy with `llmwiki remove`; remapped references to the kept pages by chunk name, then title; removed the three stale siblings; re-harvested candidates offline.
- Demo lint 0 errors / 0 warnings (was 88 / 95 after the raw refresh). Search baseline re-recorded after explaining the change: MRR 0.990, no title shared by two pages.

## gates
- `ruff check llmwiki tests scripts` — clean.
- `python3 -m pytest tests/` — green.
- `python3 scripts/release_demo_gate.py --today 2026-09-28` — passed.
