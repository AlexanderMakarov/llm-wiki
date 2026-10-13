# Flow log: 327-doctor

## fetch-ticket
- Issue: #110 — feat: `llmwiki doctor`
- Labels: enhancement, self-heal → `/implement-feature`
- Comment: provenance guided repair under doctor (#122)

## resume-detection
- Issue open; spec dir created as `327-doctor`

## workspace
- Branch: `feat/110-doctor`
- Worktree: `.claude/worktrees/feat-110-doctor`
- Throwaway vault: `.worktree-vault`

## specs
- `/awos:spec` amended to heal loop; functional **Approved**
- Locked: 1a consent; 2c all tiers runnable when confirmed; 3c default heal + `--check`/`--dry-run`; 4a exit codes secondary; 5a unknown = ticket+AI only
- Tech thickened: LLM spend policy; release-shipped JSON KB; ID-first matching + fingerprint/patterns/aliases + optional high-threshold lexical fallback (**no** doctor semantic/embedding engine); in-process then `sys.executable -m llmwiki`; **never sudo**
- Tech: `technical-considerations.md` (**Approved**); CONTRIBUTING TL;DR #14 + *CLI error strings and the doctor heal catalog*; agent pointers (not vault `AGENTS.md`)
- Amendment: KB is **current-package only** — no retired/deprecated museum; code↔`heal_kb.json` drift is a bug; delete removed failure entries
- `/awos:tasks` → `tasks.md` (7 slices; QA = testing-expert; Python = python-pro)
- Operator LGTM on tech/KB policy
- Next: commit specs → `/awos:implement`
