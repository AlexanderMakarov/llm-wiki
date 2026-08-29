# Flow log: 176-cursor-ide-ingest

## 2026-08-28 — fetch-ticket + workspace (partial)

- **Ticket:** [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) — Cursor IDE sessions not ingested
- **Branch:** `feat/2-cursor-ide-ingest`
- **Worktree:** `.claude/worktrees/feat-2-cursor-ide-ingest`
- **Throwaway vault:** `.worktree-vault/` (worktree `config.json`)
- **Mistake:** First draft lived under `context/spec/2-cursor-ide-ingest/` (issue number, not AWOS index). Removed.

## 2026-08-29 — functional-spec revision

- **Spec dir:** created via `.awos/scripts/create-spec-directory.sh cursor-ide-ingest` → `context/spec/176-cursor-ide-ingest/` (next sequential `NNN-`, not `002-`; `002-ci-refactor-ci` is a different feature)
- **Content revisions from operator:**
  1. **Archived threads:** ingest them; same `composerId` before/after archive (do not skip).
  2. **Project identity:** align with `cursor_cli`’s `cursor-<12-char-workspace-hash>` when the workspace hash is known (#126 prep; full aggregation still out of scope).
- **Next:** User approval of `functional-spec.md`, then `/awos:tech`

## 2026-08-29 — functional-spec approved + tech draft

- Operator: **lgtm** on functional-spec → Status **Approved**
- Wrote `technical-considerations.md` (Draft): synthetic composer paths + BaseAdapter `session_mtime`; global `cursorDiskKV` parse; archived included; `cursor-<hash[:12]>` shared with `cursor_cli`; R6 empty-parse warning
- **Next:** User approval of tech spec, then `/awos:tasks`

## 2026-08-29 — tech revision (operator feedback)

- **Session discovery:** replace Cursor-only `session_mtime` hack with first-class `SessionRef` + `discover_session_refs` on BaseAdapter (DB-row / non-file sessions; no stub files).
- **Testing:** probe local Cursor install first; synthetic fixtures from observed schema only.
- **Headless:** in scope — separate spawned IDE agents from user-facing Composer (R5b); markers from local probe.
- Functional-spec amended (R5b + scope); tech draft updated — re-approval needed.

## 2026-08-29 — tech approved + tasks

- Operator: **lgtm** on revised tech → Status **Approved**
- Wrote `tasks.md` (7 slices: SessionRef → local probe → IDE parse → slug → headless → R6/docs → feature testing)
- **Next:** Commit specs (Step 5), then `/awos:implement`
