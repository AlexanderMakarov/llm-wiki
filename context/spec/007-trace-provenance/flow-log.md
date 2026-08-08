# Flow log — 007-trace-provenance (#122)

## fetch-ticket / resume-detection
- Issue #122 OPEN: feat: trace a wiki page back to its raw material via source_file
- No existing spec; no PR for this work (PR #124 is #102).
- Decisions from user: MCP required; thin CLI yes; site = lightweight Source/Raw links; downward only; full chain with titles+paths; missing hops marked; any page kind with provenance.
- Next: workspace + specs

## workspace
- BRANCH=`feat/122-trace-provenance`
- WT=`/home/i4ellendger/code/llm-wiki/.claude/worktrees/feat-122-trace-provenance` (from `origin/main` @ 853faa6)
- TMP_VAULT=`$WT/.worktree-vault`; worktree `config.json` points at TMP_VAULT
- Dirty primary checkout noted (untracked screenshot; behind origin before fetch) — work proceeds in worktree only.
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
