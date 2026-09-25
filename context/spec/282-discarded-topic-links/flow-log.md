# Flow log — #282 discarded topics keep producing broken wikilinks

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/282 (OPEN, no labels, no comments)
- Symptom: `lint` link_integrity warnings dominated (97%) by links to discarded candidates under `wiki/archive/candidates/`; count grows every synth
- Causes named in issue: (1) synth vocabulary (`_inject_vocabulary` → `build_topic_graph` → `derive_vocabulary`) still offers discarded topics; (2) `candidates.discard()` leaves `[[X]]` links behind; (3) no discard-with-redirect to an existing page; (4) `/` in candidate name creates a folder; (5) case variants counted separately
- Wanted: discard-name exclusion (case-insensitive) in vocabulary + harvest; discard rewrites links to plain text or `--redirect P`; `migrate discarded-topic-links [--dry-run]`; filename sanitization; fixtures via real code paths; no LLM calls
- Related: #146 (OPEN, harvest re-proposes discarded), #139 (CLOSED, `## Aliases` resolver — redirect should reuse it), #257, #265
- Next: resume-detection

## resume-detection
- Issue OPEN; no PR references #282
- No owning functional-spec for candidate discard; allocated fix-as-spec `282-discarded-topic-links`
- Nearby: `139-candidates-merge-aliases/notes.md` (alias map: `build_page_alias_map` / `resolve_wikilink_target`), `204-harvest-case-collision`, `257-synth-vocab-kind`
- Next: workspace

## workspace
- BRANCH=`fix/282-discarded-topic-links` from origin/main 176a496
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/fix-282-discarded-topic-links` (absolute; §10 #213)
- TMP_VAULT=`$WT/.worktree-vault` + worktree `config.json`; `init` seeded
- Next: diagnose

## diagnose
- Repro scripts (scratchpad, not committed): real `harvest_targets` / `write_stubs` / `discard` / `derive_vocabulary` / `_inject_vocabulary` / `LinkIntegrity` on tmp fixtures
- D1 reproduced: `topics.py:derive_vocabulary` `dropped` fed only by `.llmwiki-topics.json`; discarded `Junk` stays in vocab + `_inject_vocabulary` output
- Harvest: `candidates_harvest.py:harvest_targets` already treats `wiki/archive/**` stems as resolved (norm-folded) — but slash names re-proposed (archived stem `B thing` ≠ `A/B thing`)
- D2 reproduced: `candidates.py:discard` → `_archive_candidate` moves file + reason.txt only; `[[Junk|the junk]]` survives
- D3 confirmed absent: CLI / `candidates_site` batch + UI carry only `reason`; `_record_alias` + `build_page_alias_map` exist (#139) but alias lookup is exact-case
- D4 reproduced: `write_stubs` builds `candidates/<kind>/A/B thing.md`; nested stub invisible to `list_candidates`, wrong "Original path", empty dir left
- D5: vocab already case-folds (`_cluster_aliases`); lint `link_integrity` uses exact-keyed `count_source_refs` so split spellings fall under `min_refs` and are suppressed
- Next: classify

## classify
- Verdict: conformance-class, orphan — no pre-existing functional-spec owns candidate discard; record "no functional-spec to amend"
- SPEC_NAME=`282-discarded-topic-links`
- Scope: full issue acceptance (D1–D5 + `migrate discarded-topic-links` + `--redirect` in CLI/batch/UI); #146's "read the recorded reason" part stays out of scope — only the shared discarded-names helper overlaps
- Next: fix

## fix
- Specialist subagent implemented all 9 tasks; it was cut off by an API spend limit before its hand-back report, so the tree was checked directly: ruff clean, full pytest green
- New: `llmwiki/migrate_discarded_topic_links.py` (`migrate discarded-topic-links --vault [--dry-run] [--redirect NAME=PAGE ...]`), `candidates discard --redirect PAGE`, batch/UI `redirect` field, flat `candidate_filename` sanitizer, shared discarded-names exclusion in `derive_vocabulary` + harvest, case-folded alias lookup, lint refs folded by `norm_page_key`
- Docs: CLAUDE.md archive note, UPGRADING, CHANGELOG, docs/reference/{cli,ui}.md, agent-kit wiki-candidates
- Follow-up: `record_redirect_alias` hard-coded "(0 source pages)" — delegated fix to pass the real count
- Next: regression-test

## regression-test
- Covered in the fix: tests in test_candidates / _harvest / _site / test_topics / test_wikilinks / test_lint_min_refs / test_archive_cold_storage + new tests/test_migrate_discarded_topic_links.py (fixtures via real `harvest_targets`/`write_stubs`/`discard`; LLM backend patched to raise)
- Next: verify-criteria

## verify-criteria
- Drove the real CLI on `$TMP_VAULT` with the fixture built by the real harvest:
  - AC1 discard → vocab: `derive_vocabulary` → `['code-foo', 'Ghost']`; `Junk`/`junk`/`JUNK` and `A/B thing` absent; `Foo` folded into `code-foo` — PASS
  - AC2 discard unlinks 3 links (label kept: "the junk"); `--redirect code-foo` gives `[[code-foo|Foo]]`/`[[code-foo|foo]]` + `## Aliases` on the project page — PASS
  - AC3 migration: dry-run byte-identical snapshot; real run unlinked 2 + flattened `X/Y.md`→`X-Y.md`; second run "nothing to migrate", snapshot identical; lint link_integrity 0 — PASS
  - AC4 `A/B thing` stub written as `candidates/entities/A-B thing.md`, listed, discard unlinks its links — PASS
  - AC5 no LLM: tests patch the synth backend to raise — PASS
- Observed: harvest picks one spelling on a case tie (`JUNK`); `--slug` matches the listed stub name exactly (`--slug Junk` → not found). Left as is; noted for the smoke step
- Next: smoke confirm → local-review

## fix (follow-ups, post-verify)
- `record_redirect_alias` now takes `source_count` (merge's `_evidence_source_slugs` meaning, computed pre-rewrite); added `archived_candidate_source_count` for the migration path — the alias line no longer says "(0 source pages)"
- User asked for `discard --slug` to match case-insensitively → implemented in the shared `_find_candidate`: exact filename wins, else a unique `norm_page_key` fold (so `Junk`→`JUNK.md`, `A/B thing`→`A-B thing.md`), else `ValueError` naming every colliding stub. Kind filtering preserved in both passes. Outside #282's acceptance — call out in the PR body
- Follow-on gap found by driving the CLI: `promote` / `flip-promote` / `merge` printed a raw traceback for an unknown or ambiguous slug (pre-existing for not-found; the new ambiguity error would land there too). Now all catch `(FileNotFoundError, ValueError, …)` → `error: …` + exit 2, keeping `KeyFactsBackendError` behavior. `rewrite-key-facts` resolves via `_find_trusted_page` (no fold) and was left alone
- Verified via the real CLI on a scratch vault: case variant, slash name, ambiguity (exit 2, both paths named), unknown slug, and no traceback on any of promote/flip-promote/merge
- Note: a full-suite run that overlapped a subagent's edits reported 3 collection ERRORs (test_synthesize_estimate, test_topic_project_routing, test_watch_adapters); all pass in isolation — re-run clean with no concurrent writers
- Next: smoke confirm (live vault, user) → local-review

## local-review
- Independent reviewer (no focus hints): Request changes — 3 Blockers, 11 Nits; review file session-only (gitignored), full body printed in chat for keep/drop
- Gates it confirmed: ruff clean, full pytest exit 0, no import cycle, no new deps, no XSS, nothing from DECLINED.md; demo-vault build diffed branch vs origin/main — topic pages / graph / search index byte-identical (vocabulary change is a no-op on a vault with no archived candidates)
- Operator keep/drop: B2 → frame the PR as a general link-integrity fix, not only the issue's case. B3 → fix in code, applying DRY (one shared slug→page resolver). N1 → deeper audit: verify every #282 CHANGELOG/CLI claim and dedupe logic across CLI pieces. Apply N2–N7, N10, N11. N8+N9 → both applied after clarifying they are separate concerns (N8 = link-identity fold, N9 = filesystem portability; neither imposes a slug spec)
- B1 (no commits) is procedural — commit stage is next; `context/spec/282-discarded-topic-links/` must be staged or the AWOS context gate fails
- B2 note: `_PAGE_KEY_RE` `[^a-z0-9]`→`[\W_]` is load-bearing, not creep — under the old regex every all-Cyrillic name folds to `""`, so the new fold-based lookup would collide them all
- Batch 1 dispatched: B3 shared resolver + containment, N1 audit, N8 (NFKC+casefold), N9 (trailing dots + Windows device names). Batch 2 (N2–N7, N10, N11) runs after, serialized to avoid concurrent edits to candidates.py
- Next: apply batch 2 → re-run gates → smoke confirm (live vault, user) → commit-push

## review-fixes
- Batch 1: `_resolve_page_file` + `_contained` backstop shared by `_find_candidate` / `_find_trusted_page` / `merge --into` / `find_live_page`; `rewrite-key-facts` now folds too (docs claim made true, not deleted); its branch also lacked `ValueError` handling — fixed; `norm_page_key` = NFKC + casefold (no migration: all uses in-memory); `candidate_filename` strips leading/trailing dots+spaces and suffixes Windows device names
- Batch 2: `rewrite_wikilinks(self_stem=)` stops self-linking a redirect target (N2); `discard` refuses a redirect when another live page owns the name, before the move (N3); `format_alias_bullet` + last-em-dash split make alias records round-trip (N4); skipped unreadable pages surfaced via `DiscardResult.skipped` / `report["errors"]` (N5); `report["skipped"]` for an unneeded redirect (N6); `DiscardBatch` + `rewrite_links_in_wiki` cut a batch from 2N wiki walks to 2 (N7); fenced-block limitation documented (N10); `run_migration` validates every `--redirect` before writing anything (N11); `check_redirect_action` dedupes the 3 copied guards and the CLI now refuses `--redirect` on non-discard actions
- Independently re-verified through the real CLI on scratch vaults: `../../outside` refused on every action with the outside file untouched; `rewrite-key-facts --slug real` resolves `REAL.md`; NFC==NFD and `Straße`==`STRASSE`; redirect target keeps its own mention as plain text; em-dash name re-runs report unchanged; bad `--redirect` exits 1 writing nothing (clean run exits 0); `promote --redirect` exits 2
- Gates after both batches (no concurrent writers): `ruff check` clean; full `pytest` exit 0, 0 `^FAILED|^ERROR`, no F/E progress markers
- Deferred by operator decision: none of the applied set. Not applied: nothing from the review except fence-skipping (docstring instead, N10) — N7 was applied, not deferred
- Known leftovers recorded by the batches: `archived_candidate_names` skips surface only to callers passing `errors` (harvest does not); `_reconcile_catalog` still runs per row inside a batch
- Next: commit-push (this is the log's last committed state) → live smoke confirm (user) → PR

## smoke-confirm (live vault)
- Backup taken before any write (wiki.tgz + llmwiki-state.json); vault at 1041 pages, 712 `link_integrity` issues
- Dry run wanted 955 unlinks across 457 pages. Evaluation of the 15 archived names against live pages + recorded reasons found 4 that were **merged**, not discarded, whose survivor no longer answers (merges predate #139 alias recording): `Kbbuilder`→`code-kbbuilder` (315), `Wikilinks`→`WikiLink` (259), `Model Context Protocol`→`MCP` (12), `GSD-Workflow`→`GSD` (1). The other 11 carry deliberate reasons ("textbook-generic concept", "tool-name artifact", "not a concept", "too broad") — unlinking is correct for them
- First operator run lost the `--redirect` flags to a paste/line split (`--redirect: command not found`) and unlinked all 955; restored from the backup and re-ran from a script (single line) — no data lost
- Result: 587 redirected + 368 unlinked + 1 nested stub flattened; aliases recorded on all 4 targets; display text preserved; zero self-links on targets (N2 holds on real data); second run "nothing to migrate"; `build` clean (1364 HTML); `link_integrity` 712 → 2 (both unrelated genuine breaks)
- Finding worth acting on: a name whose archive reason records a merge but whose survivor no longer answers is treated exactly like noise, so a default run silently flattens links a redirect would preserve. Proposed guard: print it as a suggested `--redirect` and refuse to unlink those without an explicit redirect or `--force`
- Next: decide the guard, then push + PR

## merge-guard (post-smoke hardening)
- Operator chose "guard + refuse" after the live run showed a default migration silently flattens links a redirect would preserve
- `merged_intents(wiki_dir)` reads the merge target from the archived stub's reason file through the same formatter `merge` writes it with (`_MERGE_REASON_PREFIX` / `_format_merge_reason` / `_parse_merge_reason` + `_reason_field`), so reader and writer cannot drift; `redirect_target_pages` exposes the pool `find_live_page` searches, so a suggestion can only name a page `--redirect` would accept
- `run_migration` partitions: a discarded name whose reason records a merge, that no live page answers, with no `--redirect` given → links left alone, reported with a ready-to-paste `--redirect`, exit 1. `--force` unlinks them like a dismissal. Plain dismissals, explicit redirects and the flatten pass still run in the same call
- Convergence defect caught by re-running the guard against the pre-migration snapshot: zero-link recorded merges kept the run permanently at exit 1 (the intended apply and every re-run), contradicting documented idempotence. Fixed — link counts are probed before the actionable decision, and a zero-link merge is neither reported nor exit-affecting
- Verified on the real pre-migration snapshot: guard dry-run exit 1 listing only the 4 linked merges; apply with the 4 suggested redirects exit 0 (587 redirected / 368 unlinked); immediate re-run exit 0 "nothing to migrate"; `link_integrity` 2 — matching the live vault outcome
- Next: commit-push → PR
