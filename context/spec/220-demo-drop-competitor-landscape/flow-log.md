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
- Next: commit specs, then `/awos:implement`
