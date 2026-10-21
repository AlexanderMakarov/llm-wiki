# Flow log — 220-demo-drop-competitor-landscape

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/220
- Labels: docs, minor, self-heal (no `bug` → `/implement-feature`)
- Comments: none
- Next: resume-detection / workspace

## resume-detection
- Issue state: OPEN
- No existing `context/spec/*220*` artifacts; no open/merged PR owning #220
- Next: workspace

## workspace
- BRANCH: `feat/220-demo-drop-competitor-landscape`
- WT: `.claude/worktrees/feat-220-demo-drop-competitor-landscape`
- TMP_VAULT: `$WT/.worktree-vault`
- Next: specs (`/awos:spec` approval gate)

## specs (functional — awaiting approval)
- Wrote `functional-spec.md` (Status: In Review) — **paused**: operator asked whether remove vs update is correct
- Verified correction vs issue premise: `docs/competitor-landscape.md` still exists on `main` and is still linked from `docs/index.md`; demo still has `raw/docs/competitor-landscape/` + wiki sources
- Getting-started sync hint still shows `<vault>/raw/sessions/<project>/*.md` while product sync writes flat `raw/sessions/*.md`
- Removal-rationale dig (2026-10-20):
  - No merged commit ever deleted the file; no DECLINED/roadmap entry against shipping this markdown page (DECLINED `/vs/` #138 is a different surface)
  - Issue #220 (AlexanderMakarov, 2026-09-06) asserts removal already happened + "maintainer working notes outside git" — that state never landed on `main`
  - Local `stash@{0}` `wip-before-release-2026-09-07` *did* delete the doc + delink `docs/index.md` (unpushed WIP); `tmp/competitor-landscape.md` holds a newer draft (11 agents, 3.12+, dropped comparisons/questions page-kinds) never promoted back to `docs/`
  - `.remember/today-2026-09-04.done.md` records *updating* the page (4 stale claims) two days before the issue — pattern was refresh, not retire
- Operator (Alexander Makarov — same person as issue author; local git `user.name` is nickname `4ellendger`, not a second account) chose **keep + update**
- Rewrote `functional-spec.md` for update + demo refresh; Author set to Alexander Makarov
- Functional-spec **Approved** (operator chose 1)
- Next: `/awos:tech`

## specs (technical — awaiting approval)
- Wrote `technical-considerations.md` (Status: In Review): promote tmp draft → docs; flat path hint; merge synthesis into worktree config; `refresh_demo.py` remove→add; CHANGELOG; i18n + getting-started “6 agents” out of scope by default
- Explore: no tests assert competitor-landscape by name; README = 11 agents; refresh mutates `demo/` only
- Operator asked to also compare lucasastorian/llmwiki, Obsidian karpathywiki, rohitg00/agentmemory, TencentDB Agent Memory
- Amended functional-spec requirement 2 and technical “Four new comparison columns” (facts checked 2026-10-21; no marketing stats)
- Operator: one table for the most similar active tools; short notes under the table for fresh-but-different tools; drop tools with no change in the last month
- Locked 2026-10-21: table = this repo + lucasastorian/llmwiki + Obsidian karpathywiki; under table = mem0, agentmemory, TencentDB; drop Rewind/Limitless (sunset 2025-12), Pieces (last update 2026-05-01), manual-notes column
- Tech spec **Approved** (operator chose 1 on the function grid)
- Next: `/awos:tasks`

## specs (tasks — no approval gate)
- Wrote `tasks.md`: Slice 1 docs+changelog, Slice 2 demo refresh, Slice 3 existing-suite regression (no new prose-only test, per approved tech spec). QA agent `testing-expert` is hired, so no hire question.
- Specs committed `b084dda` on `feat/220-demo-drop-competitor-landscape` (branch was already 3 behind `origin/main`; rebase before PR)
- Next: `/awos:implement`

## implement
- Slice 1 done: `docs/competitor-landscape.md` function grid; getting-started flat path; CHANGELOG under `### Changed` (first draft had landed under Added; moved)
- Slice 2: `refresh_demo.py --dry-run` listed competitor-landscape remove→add **plus 14 other docs** already stale vs `demo/.demo-source-rev` (pin `c8d74d4`, unrelated to this issue). Did **not** run the full refresh and did **not** advance the pin (that would hide those other stale docs). Scoped `remove` + `add` + `synth --docs-only --path` to `competitor-landscape` and `getting-started` only. Repointed three leftover wikilinks (Obsidian, Claude Code, CLAUDE.md candidate) at the new single-file source pages. `lint --rules link_integrity,orphan_detection,index_sync` on `demo`: 0 issues. Deleted an empty untracked `demo/wiki/archive/candidates/dismissals.json` so it is not committed.
- Worktree `config.json` has `synthesis.backend=claude` and throwaway `vault.default_path`; live vault path scrubbed. Not committed (gitignored).
- Next: slice 3 pytest, then `/awos:verify` and smoke confirm before review/commit of the product diff

## verify
- Operator accepted the comparison page (lgtm, 2026-10-21) after the eleven-row grid.
- Specs rewritten to that grid (functional requirement 2, technical comparison layout).
- Demo competitor-landscape removed and re-added, then `synth --docs-only --path`. Lint `link_integrity,orphan_detection,index_sync`: 0 issues. Search baseline test passed. `.demo-source-rev` not advanced.
- Next: local review

## local-review
- Review file: `context/spec/220-demo-drop-competitor-landscape/review.md` (gitignored, not committed)
- Verdict: Comment. Blockers 0. Nits 4.
- Next: operator keep/drop per finding, then static gate, then commit. PR link keyword to decide at commit: `Closes #220` if the corrected delivery (page kept and refreshed, demo consistent, flat path hint) completes the issue; the ticket’s “already removed” premise is false and should be noted in the PR summary.

## keep-drop
- Operator: keep all four nits.
- N3 correction from the operator: TencentDB does cover Claude Code. Count is 9 named clients from `feat/server_team` INSTALL.md (Claude Code, CodeBuddy, WorkBuddy, Codex, DeepSeek Harness, OpenCode, Hermes, OpenClaw, Pi). The Chinese `agents/README.md` lists 7 of those and omits OpenCode and Pi. Applied the install-guide list. Demo competitor page re-synthesized. Empty `dismissals.json` removed. Stray gitignored `wiki/` at the worktree root removed (it failed `test_demo_is_a_self_contained_vault`).
- Changelog bullet moved into the existing `[Unreleased]` `### Changed` section. Release note names the eleven functions and the four columns. Slice 1 task text rewritten to the locked grid.
- Static gate: `ruff check llmwiki tests scripts` passed. Full pytest failed only `test_demo_is_a_self_contained_vault` (stray `wiki/`) and `test_add_dry_run_local_md` (state mtime raced with a parallel demo build). Both re-run green after removing `wiki/` and with no parallel build.
- Issue link: `Closes #220`. The issue asked to drop a page that was never removed. The author chose keep-and-update. This PR delivers that: current comparison, demo copy in sync, flat getting-started path. The false “already removed” premise is in the PR summary.
- Next: commit, rebase onto origin/main, push, PR, CI. Do not merge until the operator says so.
