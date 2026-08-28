# Flow log — #182 configurable adapters

## 2026-08-28 — fetch-ticket

- **Ticket:** [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) — feat: make every shipped session source configurable in config.json and opt-in during install
- **State:** OPEN (no merged PR; no prior spec)
- **Branch:** `feat/182-configurable-adapters`
- **Worktree:** `.claude/worktrees/feat-182-configurable-adapters`
- **TMP_VAULT:** `.claude/worktrees/feat-182-configurable-adapters/.worktree-vault`
- **Related:** #180 merged (headless); #2 out of scope (Cursor IDE)

## 2026-08-28 — workspace

- Created worktree from `origin/main` @ db921b5
- Ran `bash setup.sh`, throwaway vault + `config.json` in worktree

## 2026-08-28 — commit-push (pre-PR)

- Implemented: `adapters/settings.py`, `configure-sources`, wired sync/adapters/watch/status
- Docs + CHANGELOG + UPGRADING updated; tests green locally
- **Next:** user smoke confirm → local review → push → PR (#182)

## 2026-08-28 — local-review

- Independent review pass complete → `review.md` (session-only, gitignored)
- **Verdict:** Request changes
- **Blockers:** 0
- **Important:** R6 doc sweep (core/contrib stale text); R4 gaps (not_detected path prompt, post-save adapter table, `setup.bat`); ChatGPT `present` column; test gaps
- **Next:** user keep/drop on review findings → fix Important items → push → PR
