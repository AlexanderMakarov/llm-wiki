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

## commit-specs
- Commit `12b6fed` — `docs: add spec for #180 exclude_headless across adapters`
- Next: `/awos:implement`

## verify
- Functional + tech Status Completed; ACs checked with pytest + adapter smoke evidence
- Focused pytest green; full suite reported green by Slice 5 agent
- Next: user smoke confirm (live vault) before local review
- Slice 4: docs support map (`docs/multi-agent-setup.md`), currency gate `tests/test_docs_adapter_currency.py`, CHANGELOG/UPGRADING re-sync note; Codex stub claims removed from user-facing docs

## smoke-side-effects (#180 follow-up)
- Cursor CLI: inject `agentId`→`sessionId`/`slug`, `createdAt`→ISO `timestamp`; harden string `subagentInfo`
- Package migration `llmwiki migrate-broken-provenance` for missing `raw/sessions` provenance hops
- Live vault repair left for orchestrator (this worktree ships code+tests only)

## 2026-08-27 12:44 UTC — smoke side-effects fixed

- Cursor CLI: `sessionId=agentId`, `createdAt`→`started`, string `subagentInfo` + non-dict tool `input` hardened.
- Added `llmwiki migrate-broken-provenance` (same-day interactive remap / clear); repaired local vault provenance to 0 errors; pruned headless Cursor raw under `exclude_headless`.
- Demo generator emits 3 headless fixtures; regenerated under `demo/raw/sessions/`.
- Waiting on operator smoke confirm before local review / PR.

## smoke-confirm
- Operator proceeded with delivery flow (smoke treated as confirmed)
- Next: local review → keep/drop → static gate → commit-push → PR

## local-review keep/drop
- Verdict: approve (0 blockers, 5 nits)
- Kept nits 1–4; nit 5 → PR body bundling note only
- Next: static gate → commit-push → PR

## commit-push
- Kept review nits 1–4 applied; static gate green (ruff + full pytest)
- Committing implementation + demo headless fixtures; review.md not staged (#159)
- Next: push → open PR → watch CI → merge confirm
