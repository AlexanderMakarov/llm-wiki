# Flow log — #249 session description (assigned names + structural fallback)

- **SPEC_NAME:** `249-session-description`
- **TICKET_ID:** 249 (merges closed #250; addresses #246 symptom)
- **Branch:** `fix/246-session-description-selection` (name kept per operator)
- **Worktree:** `.claude/worktrees/fix-246-session-description-selection`
- **TMP_VAULT:** `.worktree-vault` under worktree
- **Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/249

## Stages

### fetch-ticket (done)
- Combined feature #249; closed #250 as absorbed; commented on #246.
- Discarded prior English-heuristic WIP on this branch (reset to origin/main tree).

### resume-detection / workspace (done)
- Reusing existing worktree + throwaway vault; branch unchanged.

### specs — functional-spec (approved)
- Decisions: truncate **120**; second adapter **Cursor CLI**; fallback = **score all real user prompts → top** (maintenance-only `/mcp` may win). Status → Approved.
- Next: technical-considerations approval.

### specs — technical-considerations (approved)
- Operator LGTM on revised Part B (per-adapter normalize; type bands; position ≫ length 0..120; eval gate).

### specs — tasks (written)
- `tasks.md` slices 1–5 (hooks → scored derive → eval → docs → regression).
- Next: commit-specs → implement Slice 1.
