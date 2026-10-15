# Tasks: Session token usage store + Cursor CLI capture (#325 / spec 328)

- **Spec:** `328-cursor-cli-token-usage`
- **Status:** Implementation complete (pending full suite + PR)
- **Worktree:** `.claude/worktrees/feat-325-cursor-cli-token-usage`
- **Vault:** `$WT/.worktree-vault` only for mutating `llmwiki` commands

---

- [x] **Slice 1: Cursor inclusive→disjoint usage map (pure)**

  - [x] Add helper (`llmwiki/cursor_token_usage.py`) that maps Cursor hook/`TurnEndedUpdate` fields to Claude `message.usage` per tech spec; return `None` for occupancy-only / empty. **[Agent: python-pro]**
  - [x] Unit tests: inclusive subtract+clamp; missing fields; never invent from occupancy fixture. **[Agent: python-pro]**
  - [x] Verify: targeted pytest + ruff on touched files. **[Agent: python-pro]**

- [x] **Slice 2: Single-file `usage/session-tokens.json` upsert store**

  - [x] Implement `llmwiki/session_tokens_usage.py`: load/save atomic RMW; upsert by session_key with fingerprint skip; last_activity UTC day attribution; rebuild aggregates; sidecar emitter. **[Agent: python-pro]**
  - [x] Unit tests: idempotent upsert; day move on resume; all-skip leaves file mtime unchanged; metrics_only stub. **[Agent: python-pro]**
  - [x] Verify: targeted pytest + ruff. **[Agent: python-pro]**

- [x] **Slice 3: Wire Cursor CLI + convert/sync write path**

  - [x] `cursor_cli.normalize_records`: attach mapped usage when present; never occupancy. **[Agent: python-pro]**
  - [x] Convert upserts usage store on sync (synced + metrics_only for filtered measurable). **[Agent: python-pro]**
  - [x] Tests in `tests/test_session_tokens_wiring.py`. **[Agent: python-pro]**
  - [x] Verify: targeted pytest. **[Agent: python-pro]**

- [x] **Slice 4: Named migrate for historical backfill**

  - [x] Register `llmwiki migrate session-tokens`; `llmwiki/migrate_session_tokens.py`; cli.md + UPGRADING. **[Agent: python-pro]**
  - [x] Tests: migrate from raw frontmatter; catalog acceptance includes name. **[Agent: python-pro]**
  - [x] Verify: targeted pytest. **[Agent: python-pro]**

- [x] **Slice 5: Analytics / widgets consume usage file + coverage hover**

  - [x] Build/Analytics prefer usage file; sidecar on build; measured/known coverage lines; Cursor coverage copy updated. **[Agent: python-pro]**
  - [x] Tests for hint format and usage-file preferred stats. **[Agent: python-pro]**
  - [x] Verify: targeted pytest. **[Agent: python-pro]**

- [x] **Slice 6: Docs + I/O rules + CHANGELOG**

  - [x] state-persistence, ui, cli, UPGRADING, CONTRIBUTING Vault I/O, maintainers ARCHITECTURE, CHANGELOG. **[Agent: general-purpose]**
  - [x] context/ touched (this tasks + specs). **[Agent: general-purpose]**

- [x] **Slice 7: Feature testing & regression**

  - [x] Full `ruff check llmwiki tests scripts` + `python3 -m pytest tests/ -q` green. **[Agent: testing-expert]**
