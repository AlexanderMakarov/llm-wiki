# Flow log — 007-trace-provenance (#122)

## fetch-ticket / resume-detection
- Issue #122 OPEN: feat: trace a wiki page back to its raw material via source_file
- No existing spec; no PR for this work (PR #124 is #102).
- Decisions from user: MCP required; thin CLI yes; site = lightweight Source/Raw links; downward only; full chain with titles+paths; missing hops marked; any page kind with provenance.
- Next: workspace + specs

## workspace
- BRANCH=`feat/122-trace-provenance`
- WT=`.claude/worktrees/feat-122-trace-provenance` (from `origin/main`)
- TMP_VAULT=`$WT/.worktree-vault`; worktree `config.json` points at TMP_VAULT
- Dirty primary checkout noted (untracked local artifact; behind origin before fetch) — work proceeds in worktree only.
- Next: specs (`/awos:spec`)

## specs — functional
- SPEC_NAME=`007-trace-provenance`
- `functional-spec.md` approved; later revised (MCP drop, site Sources links, FR lint + doctor #110) and re-approved via redesign answers.
- Next: `/awos:tech` (approval gate)

## specs — technical
- `technical-considerations.md` approved (shared `trace.py`; CLI; site Sources links; lint `provenance_integrity`; no new MCP; doctor heal on #110).
- Comments posted on #110 and #122.
- Next: `/awos:tasks` (no draft gate under implement-feature)

## specs — tasks
- `tasks.md` written (6 slices). Draft Approve loop suppressed per delivery-flow Local Customization.
- Next: commit-specs then `/awos:implement`

## implement — Slice 6 feature/regression testing
- Next: feature testing + acceptance

## perf fix — source_file index (#122)
- Live vault build ~117 min / ~1029 sessions traced to `find_wiki_source_for_raw` rescanning `wiki/sources/**` + parsing frontmatter per session/document page.
- Added `build_source_file_index(vault)`; threaded optional `index=` through `find_wiki_source_for_raw` / `provenance_links_for_raw`; `build_site` + `render_document_pages` build once per batch.
- Topics leave `sources_links`/`trace_page` as-is (few pages).
- Test: `tests/test_source_file_index.py` (correctness vs naive scan + call-count microbench with 50 sources).
- Next: ruff + pytest; re-time live rebuild if vault available

## local-review
- Dual review written: `review.md` (5 blockers · 8 nits), `review-code-reviewer.md` (1 critical · 3 important).
- User: fix all except nits; keep #81 on_disk in this PR with body waiver (no split).
- Applied: privacy scrub in flow-log; document Sources prefer-HTML + `.md` sibling fallback (C1/B5/I1); #81 backfill retained with waiver.
- Next: commit-push (last flow-log write before PR)

## commit-push
- Staged all #122 + waived #81 on_disk backfill; conventional commits; push branch; open PR with size/concern waivers.
- Stop appending to this tracked log after the change request is open.
