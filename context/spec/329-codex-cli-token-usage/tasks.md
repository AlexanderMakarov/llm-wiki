# Tasks: Codex CLI session Tokens capture (#324 / spec 329)

- **Spec:** `329-codex-cli-token-usage`
- **Status:** Ready for implementation
- **Worktree:** `.claude/worktrees/feat-324-codex-cli-token-usage`
- **Vault:** `$WT/.worktree-vault` only for mutating `llmwiki` commands

---

- [ ] **Slice 1: Codex → Claude usage mapper (pure)**

  - [ ] Add `llmwiki/codex_token_usage.py`: extract final `total_token_usage` (else sum `last_token_usage` once); map to Claude four fields per tech spec; omit reasoning when `reasoning_output_tokens` present; return `None` for empty / occupancy-only / rate_limits-only. **[Agent: python-pro]**
  - [ ] Unit tests in a stable slug module (e.g. `tests/test_codex_token_usage.py`): disjoint buckets + clamp; reasoning subtract; multi-snapshot no double-count; no invent from `model_context_window` / rate_limits. **[Agent: python-pro]**
  - [ ] Verify: targeted pytest + `ruff check` on touched files. **[Agent: python-pro]**

- [ ] **Slice 2: Wire `codex_cli.normalize_records`**

  - [ ] Collect `event_msg` / `token_count`; attach mapped `message.usage` so `compute_token_totals` sees it (synthetic or last assistant). Keep conversation mapping behavior otherwise unchanged. **[Agent: python-pro]**
  - [ ] Synthetic/redacted fixture JSONL under `tests/fixtures/`; adapter tests assert usage present and multi-event totals match final cumulative. **[Agent: python-pro]**
  - [ ] Verify: targeted pytest + ruff. **[Agent: python-pro]**

- [ ] **Slice 3: Convert / migrate path + coverage hint**

  - [ ] Confirm convert upserts `token_totals` + `usage/session-tokens.json` for agent `codex_cli` when usage present; empty stays omitted (no fabricated zeros). Fix wiring only if gaps found. **[Agent: python-pro]**
  - [ ] Update `TOKEN_COVERAGE_LINES`: Codex included when usage present; Cursor IDE still not captured. Adjust tests that assert the old combined string. **[Agent: python-pro]**
  - [ ] Verify: pytest for coverage strings + a convert/migrate smoke with Codex fixture into `$TMP_VAULT`. **[Agent: python-pro]**

- [ ] **Slice 4: Docs + investigation notes + CHANGELOG**

  - [ ] Write `investigation-notes.md` (verified fields, sample structure redacted, cumulative vs last, historical migrate/re-sync). Update `docs/adapters/codex-cli.md`, `docs/UPGRADING.md`, `CHANGELOG.md` `[Unreleased]`, and ui/reference coverage copy if needed. **[Agent: generalPurpose]**
  - [ ] Verify: docs mention Codex Tokens + migrate path; no personal vault paths. **[Agent: generalPurpose]**

- [ ] **Slice 5: Feature testing & regression**

  - [ ] Full `ruff check llmwiki tests scripts` + `python3 -m pytest tests/ -q` green from worktree. **[Agent: testing-expert]**
