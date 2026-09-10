# Tasks: Session description assigned names + scored fallback (#249)

- **Spec:** `249-session-description`
- **Status:** Ready to implement
- **Branch:** `fix/246-session-description-selection`
- **Worktree:** `.claude/worktrees/fix-246-session-description-selection`
- **Vault:** `$WT/.worktree-vault` only for mutating `llmwiki` commands

---

- [ ] **Slice 1: Adapter hooks — assigned name + normalize_user_prompt**

  - [ ] Add `BaseAdapter.assigned_session_name(path, records) -> str | None` and `normalize_user_prompt(text) -> str` (default identity/strip). Claude Code: `customTitle` sidecar then `aiTitle`; move Claude XML→`/cmd` into Claude `normalize_user_prompt`. Cursor CLI: persist/read store meta `name` in `assigned_session_name`. **[Agent: general-purpose]**
  - [ ] Unit tests for Claude customTitle/aiTitle precedence and Cursor meta `name`; normalize smoke for Claude envelope. **[Agent: general-purpose]**
  - [ ] Verify: targeted pytest + ruff on touched files. **[Agent: general-purpose]**

- [ ] **Slice 2: Scored `derive_description` (delete old heuristics)**

  - [ ] Remove description-path soft-ack / continuation / chrome-skip / first-match selection. Implement type bands (slash+long-args ≈ prose high; slash+short-args mid-low; bare lowest) + position + length `min(len,120)`; truncate display 120. Accept provisional weights; encode invariants in tests (`/fix-bug` > later `merge with --admin`; `/clear`+/model+/theme < later prose; `/mcp`-only → `/mcp`). **[Agent: general-purpose]**
  - [ ] Wire `render_session_markdown` / `convert_all`: assigned name (redacted) wins; else scored derive with active adapter normalize. **[Agent: general-purpose]**
  - [ ] Verify: `tests/test_session_description.py` green + ruff. **[Agent: general-purpose]**

- [ ] **Slice 3: Operator eval harness (read-only real sessions)**

  - [ ] Add a read-only script/helper that loads recent Claude Code + Cursor CLI sessions, prints assigned name / top candidates+scores / chosen `description:` (no live vault writes; no personal paths committed). Run it; present table to operator; apply weight/rule corrections; re-run until accepted; freeze weights. **[Agent: general-purpose]**
  - [ ] Verify: eval re-run matches operator-accepted outcomes on the sample; unit invariants still green. **[Agent: general-purpose]**

- [ ] **Slice 4: Docs + adapter inventory**

  - [ ] CHANGELOG Unreleased + UPGRADING (assigned names win; scored fallback; optional `sync --force`; no re-synth); adapter inventory table; touch `docs/reference` only if a sessions/description row exists. Keep `context/spec/249-session-description/` updated. **[Agent: general-purpose]**
  - [ ] Verify: docs paths exist; ruff/pytest still green. **[Agent: general-purpose]**

- [ ] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature against functional-spec.md after implementation slices.
  - [ ] Acceptance/regression tests for R1–R4 invariants; annotate `@spec: 249-session-description` where suitable. **[Agent: testing-expert]**
  - [ ] Full `ruff check llmwiki tests scripts` + `pytest tests/ -q` green. **[Agent: testing-expert]**
