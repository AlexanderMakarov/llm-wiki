# Flow log — 006-honest-synthesized-counts (#81)

## fetch-ticket
- Ticket: #81 — Honest already-synthesized counts (roadmap Phase 1)
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/81
- State: open; related #113 closed (Candidates pre-run labelling — convention to reuse)
- Scope chosen with user: relabel + labelled page/stub count; no divergence buckets; no stale-state reconcile

## resume-detection
- No prior spec for #81; next incomplete roadmap item under Honest pipeline reporting
- Entry: full chain from functional-spec

## workspace
- BRANCH: `feat/81-honest-synthesized-counts`
- WT: `.claude/worktrees/feat-81-honest-synthesized-counts`
- TMP_VAULT: `$WT/.worktree-vault`
- Base: `origin/main` @ 7158e41

## implement
- All tasks.md items `[x]` (slices 1–4)
- Code: estimate keys + CLI labels + reporting helper; pipeline/build persist; Home JS caption + note; docs/CHANGELOG/roadmap; `tests/test_81_acceptance.py`

## follow-up — build backfill for pre-#81 pipeline.rows
- Bug: `_ensure_synth_pipeline_snapshot` only checked `synth_pipeline_shape_ok`; pre-#81 rows (raw/pending/synthesized, no `on_disk`) never refreshed → Home On disk column stayed 0 while `estimate.source_pages_on_disk` was correct.
- Fix: `pipeline_rows_missing_on_disk` in `state_store.py`; `_ensure_synth_pipeline_snapshot` refreshes when any row lacks `on_disk` (or empty rows + pages on disk). Cheap path unchanged when keys present.
- Tests: `test_pipeline_rows_missing_on_disk`, `test_refresh_synth_pending_persists_pipeline_on_disk`, `test_build_backfills_pipeline_rows_missing_on_disk` (+ assert on persisted rows in `test_refresh_synth_pending_stores_source_page_counts`).

## local-review
- Dual review written: `review.md` (checklist), `review-code-reviewer.md` (code-reviewer)
- Applied: C1 agent join; N1/I2 stubs row only when stubs>0; deleted docs/screenshots PNG; PR size waiver planned
- Skipped other nits per user keep/drop
- Next: commit-push → open PR → remote gates
