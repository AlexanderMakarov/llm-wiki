# Flow log — 200-release-skill (#209)

## workspace
- Branch: `feat/209-cross-agent-release-skill`
- Worktree: `.claude/worktrees/feat-209-cross-agent-release-skill`
- Throwaway vault: `.worktree-vault`

## specs
- All Approved; tasks.md complete; committed

## implement
- Slices 1–4 done; rebased onto origin/main

## local-review
- Smoke: agent-verified (skill/wrappers/tests)
- Review: Request changes → kept B1 (stdlib frontmatter) + N1 (git add in skill fence)
- Next: commit-push → PR

## implement
- Slice 1+2: `.claude/skills/release/SKILL.md`; thin `.claude/commands/release.md` + `.cursor/commands/release.md`; rewrite `docs/maintainers/RELEASE_PROCESS.md`; update `docs/maintainers/README.md`, `docs/reference/slash-commands.md`, `docs/reference/cli.md`; `CHANGELOG.md` Unreleased; `tasks.md` Slice 1–2 checked
