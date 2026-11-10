# Flow log — #225 demo release freshness

## docs reminder (2026-09-06)
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/225 — full automated gate still open
- This change: release checklist / skill / script docs so maintainers cannot forget regenerate-before-tag; README CI Python claim fixed (stale 3.12+3.13)
- Automated stale-session CI gate left for the issue acceptance criteria

## wiki-checks shallow clone (2026-09-07)

- Symptom: after committing `demo/.demo-source-rev`, Wiki checks failed on `refresh_demo.py --dry-run` with `fatal: bad object` / `bad revision` because `actions/checkout` default depth-1 cannot resolve the recorded parent SHA or release tag.
- Fix: `.github/workflows/wiki-checks.yml` sets `fetch-depth: 0` so the dry-run plan can resolve the recorded rev. Pin `.demo-source-rev` to the v2.2.0 demo commit SHA (`5952316…`).

## workspace + functional spec (2026-11-08)
- Branch: `feat/225-demo-session-freshness-gate`
- Worktree: `.claude/worktrees/feat-225-demo-session-freshness-gate`
- MAIN: `/home/i4ellendger/code/llm-wiki`
- Remaining scope (post-#226 docs): Pages-only every-6-days session date slide; no LLM in CI; no git write (Option A); docs/usage/synth stay release-only
- Artifact: `context/spec/225-demo-release-freshness/functional-spec.md` (Approved)
- Next: `/awos:tech`

## tech + tasks (2026-11-10)
- Decisions: cron `0 4 */6 * *` (max ~7d); checkout `main` (Option 1); separate `demo-session-freshness.yml`; docs must correct “no scheduled freshness”; FR5/FR6 updated for main checkout / version may track main
- Artifacts: `technical-considerations.md` (Approved), `tasks.md` (4 slices)
- Next: commit specs → `/awos:implement`

## implement + verify (2026-11-10)
- All tasks `[x]`; functional/tech Status Completed
- TEMP: Pages upload/deploy commented in `demo-session-freshness.yml` for branch `workflow_dispatch` dry-run (restore before merge)
- Next: local review keep/drop → commit/push/PR → GH Actions dry-run on branch

## commit-push (2026-11-10)
- Keep/drop: fix N1 (stage workflow+tests) + N3 (drop duplicate #225 asserts in test_209); leave B1/B2/N2 for follow-up after Actions dry-run
- Issue link keyword for PR: `Relevant to #225` (TEMP deploy still off — not full delivery yet)
- Next: push + PR; workflow_dispatch on branch; then restore deploy (B1) + harden tests (N2); B2 pin-main dropped for branch dry-run intent
