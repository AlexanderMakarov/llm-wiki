# Flow log: 306-wiki-add-operation-result

## fetch-bug
- BUG_ID: 306
- Title: bug(mcp): wiki_add timeout loses access to the continuing operation and its final result
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/306
- State: open; labels: bug, self-heal; comments: none
- Symptom: `wiki_add` returns an error after `mcp.tool_timeouts.wiki_add` while the worker continues, but the response has no operation id, pollable state, or final result
- Related (reachable): #286 closed (bounded response + retry warning); #264 closed (known-names performance; out of scope)
- Unreachable links: none
- Next: resume-detection

## resume-detection
- Not already fixed (issue open; no PR for this completion contract)
- Owning functional spec: none. `286-wiki-add-timeout` is flow-log only (no `functional-spec.md`). Related `273-mcp-wiki-add-cli-proxy` covers MCP↔CLI add parity, not a pollable operation result
- SPEC_NAME: `306-wiki-add-operation-result` (orphan fix-as-spec, #164)
- Next: workspace

## workspace
- BRANCH: `fix/306-wiki-add-operation-result`
- WT: `/home/USER/code/llm-wiki/.claude/worktrees/fix-306-wiki-add-operation-result` (absolute; §10 #213)
- TMP_VAULT: `$WT/.worktree-vault` (absolute; worktree `config.json` is vault-only)
- Primary checkout dirty only with untracked `.automation/` — warned, not a blocker
- `context/product/architecture.md` readable
- Next: diagnose

## diagnose
- Reproduced: yes. Stubbed slow `run_add`, 0.2s budget. `tool_wiki_add` returned in ~0.2s as `{content, isError: true}` with the budget warning and no `operation_id`. Worker later had `task_id` `add-sync-999001`, not reachable from the MCP return or any MCP tool.
- Root cause: `llmwiki/mcp/server.py::tool_wiki_add` returns `_err(...)` on `TimeoutError` and drops `fut`. `llmwiki/add_pipeline.py::run_add` keeps `add-sync-*` local and does not put it on the result dict until a later `_track`.
- Existing surface: CLI `queue status` is aggregate only. `add_doc_sync` is tracking-only (not in `TASK_HANDLERS`). No MCP tool reads a queue item. Row fields lack written paths, synth errors, rollback list, and build outcome; a later `_track("error")` can overwrite a rollback `last_error`.
- Next: classify

## classify
- Verdict: orphan fix. No functional spec states the completion contract, so there is nothing to amend and no `/awos:spec` pass.
- `273-mcp-wiki-add-cli-proxy` (Completed) only names `mcp.tool_timeouts.wiki_add` (default 120s). This fix keeps that budget. It does not change CLI/MCP add parity for a finished add.
- `178-mcp-tool-consolidation` keeps six MCP tools. Status is a `wiki_add` mode (`operation_id`, no url/path/content), not a seventh tool. Not a divergence from 178.
- User docs (`docs/reference/mcp.md`) and CHANGELOG still update in the fix: published 2.4.0 already returns the bare timeout error, so a new `[Unreleased]` *Fixed* entry is appropriate (#339 does not apply).
- No §9 divergence comment.
- Next: fix

## fix
- `tool_wiki_add` mints `add-sync-<ms>` before `pool.submit` and passes it as `run_add(..., task_id=)`. CLI callers omit `task_id`; every `run_add` result includes `task_id`.
- `run_add` writes `add_doc_sync` (not in `TASK_HANDLERS`) as `running` before `add_sources`, with `detail` (`written`, `errors`, `rolled_back`, `build_failed`, `files_remain`) as vault-relative state. Every return path sets `done` or `error`. Build-only failure is `done` (CLI exit code unchanged). A specific rollback `last_error` is not replaced by `add command finished with errors`.
- Timeout returns `isError: false` pending JSON using the parent id. Poll is `wiki_add` with `operation_id` only (no pipeline lock). CLI: `queue status --id` prints the same object, exit 0 found / 1 unknown.
- In-budget success JSON gains `operation_id`. In-budget genuine failures stay prose `_err`. Continuation tests are `test_wiki_add_timeout_then_succeeds` and `test_wiki_add_timeout_then_fails` in `tests/test_mcp_wiki_add.py`.
- No seventh MCP tool. No heal-catalog row (timeout sentence was not in `heal_kb.json`).
- Also updated packaged `llmwiki-ingest` skill: on timeout, poll `operation_id` instead of reading the vault filesystem.
- Next: regression-test

## regression-test
- Extended `tests/test_mcp_wiki_add.py` (no new filename): `test_wiki_add_timeout_then_succeeds`, `test_wiki_add_timeout_then_fails`.
- Existing `test_wiki_add_timeout_returns_within_budget` now expects pending JSON.
- `python3 -m pytest tests/test_mcp_wiki_add.py`: 22 passed (reported by the test stage).
- Next: verify-criteria

## verify-criteria
- Automated: throwaway-vault `llmwiki add --no-build` wrote one raw doc; `queue status --id` printed `status: done`, vault-relative `written`, `retry_safe: false`, `build_failed: false`. Unknown id printed `status: unknown`, `retry_safe: false`, exit 1.
- Timeout-then-success and timeout-then-failure are covered by the two regression tests (a live synth over 120s would hold the operator pipeline lock).
- Operator ran the live check by asking the agent to execute it. `queue status --id add-sync-1793034428361` on the live vault returned `done`, vault-relative `written`, `retry_safe` false. Operator: lgtm.
- Next: local-review

## local-review
- Review file (session-only, not staged): `context/spec/306-wiki-add-operation-result/review.md`
- Verdict: Request changes. Counts: 2 Blocker, 1 Nit.
- Operator: B2 and N1 kept and applied. B1 kept as a single vault resolution: the first call binds `--vault` or `vault.default_path`, and state plus content use that path. No package-directory fallback.
- B2: `run_add(dry_run=True)` no longer calls `_track` / `update_state`. `tests/cli/test_add.py` asserts a missing state file stays missing and an existing file's bytes stay put. Those two tests passed.
- N1: the fix bullet now names `test_wiki_add_timeout_then_succeeds` and `test_wiki_add_timeout_then_fails`. Stage this flow-log with the product commit.
- B1 option 2 applied: `active_vault` / `bind_vault` / `resolve_vault_dir` are the one vault path. CLI, MCP, add, sync, build, synth, lint helpers, and state use it. No `--vault` and no `vault.default_path` errors with exit 2. Package / source checkout are not implicit vaults.
- Static gate: `ruff check llmwiki tests scripts` clean; `python3 -m pytest tests/ -q --ignore=tests/e2e` green.
- Issue link keyword: `Closes #306` (timeout poll contract + vault-bound operation row).
- Next: commit-push, open PR, wait for CI, ask before merge

## commit-push
- Branch: `fix/306-wiki-add-operation-result`
- Keyword: `Closes #306`
- PR: https://github.com/AlexanderMakarov/llm-wiki/pull/373
- CI follow-up: action-smoke failed — `init --vault .` refused as source checkout when `package: .`. Browser smoke failed — session-scoped e2e `build_site` hit `resolve_state_file(None)` / `VaultNotConfigured` with no bound vault. Fixed: Action `vault` input + CI `action-vault`; `build_site` reads estimate from `content_root/llmwiki-state.json`.
- CI follow-up 2: `sync --status` without vault raised Traceback on CI (no config.json); `cmd_sync_status` now exits 2 with the same error string. E2E demo walkthrough built tracked `demo/` and dirtied state/usage files — build a throwaway copy instead.
- Docs trim: shortened `docs/reference/mcp.md` timeout/poll prose and the Unreleased `#306` CHANGELOG entry to high-level wording (operator review).
- CI: Playwright job failed after pytest 9.2.0 (pytest-bdd#850 `_arg2fixturedefs`); pin `pytest>=8.4.2,<9.2` in `dev`/`e2e` extras.
