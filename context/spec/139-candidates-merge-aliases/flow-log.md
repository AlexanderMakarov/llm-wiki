# Flow log — #139 candidates merge aliases

## fetch-bug (2026-08-27)
- BUG_ID: 139
- Title: candidates merge: aliases are recorded but never resolved, so every merge creates broken wikilinks
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/139
- State: OPEN; labels: bug; no comments
- Symptom: merge writes `## Aliases` on survivor but nothing resolves them → dangling `[[merged-away]]`; evidence count not recomputed after merge
- Suggested fix (issue): resolve via Aliases OR rewrite inbound links; recompute evidence count
- Linked: demo rebuild #109 (context only)
- Next: resume-detection

## resume-detection (2026-08-27)
- Issue open; no merged PR fixing #139
- No owning functional-spec for merge/aliases → orphan SPEC_NAME=`139-candidates-merge-aliases`
- Dirty primary tree: untracked `candidates*.png` only (warn, not blocker)
- Next: workspace

## workspace (2026-08-27)
- BRANCH=`fix/139-candidates-merge-aliases`
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/fix-139-candidates-merge-aliases`
- TMP_VAULT=`$WT/.worktree-vault` (isolated config.json)
- setup via `bash ./setup.sh` (exec bit missing on setup.sh)
- Next: diagnose

## diagnose (2026-08-27)
- Reproduced: merge ObsidianWikilinks→WikiLinks; graph broken_edges + link_integrity on merged-away name; "Named by 1" with 2 sources
- Root cause: `candidates.merge`→`_record_alias` write-only; wikilink consumers stem-only; merge unions sources without refreshing harvest boilerplate
- Fix shape: alias map in `wikilinks.py` + resolve in graph/link_integrity/backlinks/references; `_refresh_harvest_boilerplate` in merge
- Next: classify

## classify (2026-08-27)
- Verdict: **conformance** (aliases already recorded as identity; consumers fail to honor them; evidence count contradicts list)
- SPEC_NAME=`139-candidates-merge-aliases` (orphan); **no functional-spec to amend**
- Next: fix

## fix (2026-08-27)
- Implemented alias parse/resolve in `wikilinks.py`; wired graph, link_integrity, backlinks, references; merge refreshes harvest boilerplate
- Next: (await regression tests in separate stage)

## fix (2026-08-27)
- Alias map + resolve in wikilinks.py; wired into graph, link_integrity, backlinks, references
- merge refreshes "Named by N" boilerplate
- Docs: CHANGELOG, docs/reference/cli.md, wiki-candidates.md; notes.md
- Next: regression-test

## regression-test (2026-08-27)
- 11 regression tests across test_wikilinks, test_lint_rules, test_graph_viewer, test_candidates, test_backlinks — all green
- Next: verify-criteria

## verify-criteria (2026-08-27)
- Criteria checked on `$TMP_VAULT`:
  1. After merge ObsidianWikilinks→WikiLinks, inbound `[[ObsidianWikilinks]]` resolves: graph 0 broken; link_integrity 0 issues; edge targets WikiLinks
  2. Survivor body: `Named by 2 source page(s)` with both evidence bullets; `## Aliases` lists ObsidianWikilinks
- Unit subset for same criteria: 4/4 passed
- Next: smoke confirm (paused for user)

## smoke / self-verify (2026-08-27)
- User asked agent to self-test (no live mutating commands)
- ruff: clean; full pytest: exit 0
- E2E vault: double-merge ObsidianWikilinks+wikilinks-alt → WikiLinks; Named by 3; graph 0 broken; link_integrity 0; linker→WikiLinks; build OK once raw session present
- Live read-only: 741 wiki pages, 0 current `## Aliases` sections (nothing to probe for old merges)
- Next: await proceed-to-local-review (or treat self-test as smoke OK)

## amend-spec (2026-08-27)
- Skipped — conformance orphan; no functional-spec to amend
- Next: local-review

## smoke confirm (2026-08-27)
- User: proceed (after agent self-verify)
- Next: local-review

## local-review (2026-08-27)
- Verdict: Comment; 0 blockers, 2 nits
- Review file: context/spec/139-candidates-merge-aliases/review.md (session-only, not committed)
- User: fix both and proceed
- Applied nit 1: orphan_detection alias resolve + test_orphan_detection_resolves_merged_alias
- Nit 2: addressed by this commit
- Next: commit-push

## commit-push (2026-08-27)
- Staging code + docs + flow-log/notes; excluding review.md, vaults, config.json
- After this entry: commit + push; stop appending tracked flow-log once PR opens
