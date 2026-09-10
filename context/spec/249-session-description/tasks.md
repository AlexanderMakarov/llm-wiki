# Tasks: Session description assigned names + scored fallback (#249)

- **Spec:** `249-session-description`
- **Status:** Slices 1–5 done; delivery (commit / PR / CI)
- **Branch:** `fix/246-session-description-selection`
- **Worktree:** `.claude/worktrees/fix-246-session-description-selection`
- **Vault:** `$WT/.worktree-vault` only for mutating `llmwiki` commands
- **Eval:** operator accepted; scoring weights **frozen** (leave `ARG_LONG_MIN` unless a test forces a change)

---

- [x] **Slice 1: Adapter hooks — assigned name + normalize_user_prompt**

  - [x] Add `BaseAdapter.assigned_session_name(path, records) -> str | None` and `normalize_user_prompt(text) -> str` (default identity/strip). Claude Code: `customTitle` sidecar then `aiTitle`; move Claude XML→`/cmd` into Claude `normalize_user_prompt`. Cursor CLI: persist/read store meta `name` in `assigned_session_name`. **[Agent: general-purpose]**
  - [x] Unit tests for Claude customTitle/aiTitle precedence and Cursor meta `name`; normalize smoke for Claude envelope. **[Agent: general-purpose]**
  - [x] Verify: targeted pytest + ruff on touched files. **[Agent: general-purpose]**

- [x] **Slice 2: Scored `derive_description` (delete old heuristics)**

  - [x] Remove description-path soft-ack / continuation / chrome-skip / first-match selection. Implement type bands (slash+long-args ≈ prose high; slash+short-args mid-low; bare lowest) + position + length `min(len,120)`; truncate display 120. Accept provisional weights; encode invariants in tests (`/fix-bug` > later `merge with --admin`; `/clear`+/model+/theme < later prose; `/mcp`-only → `/mcp`). **[Agent: general-purpose]**
  - [x] Wire `render_session_markdown` / `convert_all`: assigned name (redacted) wins; else scored derive with active adapter normalize. **[Agent: general-purpose]**
  - [x] Verify: `tests/test_session_description.py` green + ruff. **[Agent: general-purpose]**
  - [x] Operator-eval corrections (#249 follow-ups): Cursor placeholder `New Agent` → not assigned; punctuation-only candidates invalid (Unicode `isalnum`); Cursor `normalize_user_prompt` strips envelope chrome (`user_info` / `system_reminder` / …) so scored fallback is not `<user_info>`. **[Agent: general-purpose]**

- [x] **Slice 3: Operator eval harness (read-only real sessions)**

  - [x] Add a read-only script/helper that loads recent Claude Code + Cursor CLI sessions, prints assigned name / top candidates+scores / chosen `description:` (no live vault writes; no personal paths committed). Run it; present table to operator; apply weight/rule corrections; re-run until accepted; freeze weights. **[Agent: general-purpose]**
  - [x] Verify: eval re-run matches operator-accepted outcomes on the sample; unit invariants still green. Weights frozen as-is. **[Agent: general-purpose]**

- [x] **Slice 4: Docs + adapter inventory**

  - [x] CHANGELOG Unreleased + UPGRADING (assigned names win; scored fallback; optional `sync --force`; no re-synth); adapter inventory table; touch `docs/reference` only if a sessions/description row exists. Keep `context/spec/249-session-description/` updated. **[Agent: general-purpose]**
  - [x] Verify: docs paths exist; ruff/pytest still green. **[Agent: general-purpose]**

- [x] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature against functional-spec.md after implementation slices.
  - [x] Acceptance/regression tests for R1–R4 invariants; annotate `@spec: 249-session-description` where suitable. **[Agent: testing-expert]**
  - [x] Full `ruff check llmwiki tests scripts` + `pytest tests/ -q` green. **[Agent: testing-expert]**
