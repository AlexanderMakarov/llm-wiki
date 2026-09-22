# Flow log — fix #265 (source pages under stale slug)

## fetch-bug + resume-detection
- Issue #265 open; no merged PR. No owning functional spec → orphan fix-as-spec dir `context/spec/fix-265-source-page-paths/`.
- Operator goal: fix wrong pending counts / broken traceability, public migration, then clean the operator's vault with it.

## workspace
- Branch `fix/265-source-page-paths` from origin/main 4947790; worktree `.claude/worktrees/fix-265-source-page-paths`; throwaway vault `.worktree-vault`.
- Next: diagnose.

## diagnose
- Root cause: #246/#249 renamed raw session files; synth state keys (`llmwiki-state.json` synth.files) and source page filenames kept old names. Dedup guard (pipeline.py ~1715-1742) correctly refuses duplicates; nothing re-keys state or moves page. Estimate (synth/estimate.py session loop) counts them pending (state-only check).
- Side bug: numeric `slug:` parsed as int → `synth_page_filename` falls back to raw stem → doubled date filename (18 live pages).

## classify
- Verdict: orphan fix, no functional-spec to amend (new migration `migrate source-page-paths` + naming fix). Operator chose to include the numeric-slug naming fix in scope.
- Next: fix + regression tests (delegated).

## fix + regression-test
- New `llmwiki/migrate_source_page_paths.py` + CLI `migrate source-page-paths`; `synth_slug_text` fixes numeric-slug filenames; synth prints one dedup summary line. Tests: `tests/test_migrate_source_page_paths.py`, `tests/test_synth_numeric_slug.py`; ruff + full suite green (5443 passed).
- Live read-only dry-run: 41 moves, 0 collisions, 35 links + 27 sources entries rewritten, 6 ambiguous stems, 23 state upserts; live state/log mtimes unchanged.
- Decision: add backlink disambiguation for ambiguous stems (operator goal: traceability). In progress.
- Backlink disambiguation added (`_Backlinks`); suite 5447 passed. Live dry-run: 41 moves, 0 collisions, 57 links + 43 sources rewritten, 9 still ambiguous over 2 stems, 0 would break; scratch-copy real run kept link_integrity at 688→688, second run no-op.

## verify-criteria
- Acceptance checked via tests + scratch-copy run: migration moves pages, next synth prints no per-source skip line, estimate pending 23→3 (remaining 3 are #147/#257 topic rewrites), collision reported, dry-run writes nothing, second run no-op, no LLM call.
- Next: operator smoke confirm on live vault, then local review.

## smoke (operator asked agent to run it on the live vault; backup taken first)
- estimate pending 23→3 (remaining 3 = #257 topic rewrites); migrate: 41 moves, 0 collisions, 57 links + 43 sources rewritten, 0 would break; lint link_integrity 688→688, title_ambiguity 16→11; re-run "nothing to migrate"; stale scan 0; build OK; 1618 dated source links in entities/concepts all resolve.
- Next: local review.

## local-review
- Reviewer verdict: Request changes (2 blockers, 2 nits). Live vault checked: B1 did not occur (41 moved pages all real).
- Operator keep/drop: keep B1 (stub-overwrite fix + test), N1 (state upsert only when missing), N2 (transactional moves); B2 resolved by filing #279 for the numeric-slug fix and closing both #265 and #279 from this PR — operator decision: both fix stale-slug consequences, so one PR; size justified in PR body.
- Next: apply fixes, re-run gates, commit-push, open PR.
- Review fixes applied: B1 (replaced stubs excluded from rewrite pass), N1 (state upsert only when missing), N2 (moves first, per-source rollback, rewrites/state re-planned for landed moves). Full suite 5452 passed, 48 skipped; ruff clean. Filed #279 (numeric-slug) and #280 (test-suite reduction, unrelated follow-up).

## commit-push
- Branch `fix/265-source-page-paths` pushed; PR closes #265 and #279. Tracked flow-log ends here (Context Discipline).
