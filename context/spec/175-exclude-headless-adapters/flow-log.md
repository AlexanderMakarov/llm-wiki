# Flow log — 175-exclude-headless-adapters (#180)

## fetch-ticket
- Issue #180 open; title: extend filters.exclude_headless to every agentic adapter
- Related later: #2 (Cursor IDE), #182 (adapter config/install)

## resume-detection
- No prior spec/PR for #180; start from workspace

## workspace
- Branch: `feat/180-exclude-headless-adapters`
- Worktree: `.claude/worktrees/feat-180-exclude-headless-adapters`
- Throwaway vault: `.worktree-vault` via worktree `config.json`

## specs
- User clarified: Cursor Agent CLI only (not IDE); OpenClaw interactive (dreaming out of session store); Codex/other CLIs like Claude; keep current sync skip summary; docs support map + fix Codex stub; #2/#182 out of scope
- `functional-spec.md` approved 2026-08-27 — Author Aleksandr Makarov

## tech
- `technical-considerations.md` approved (lgtm) 2026-08-27
- Cursor: subagentInfo OR approvalMode=auto-review; OpenClaw always not headless (code comment only for dreaming); every adapter implements is_headless_session; docs currency grep

## tasks
- `tasks.md` written (5 slices) — no document gate under implement-feature
- Next: commit specs → `/awos:implement`
