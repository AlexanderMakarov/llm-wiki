# Flow log — 329-codex-cli-token-usage

## fetch-ticket
- Issue: #324 feat(codex_cli): investigate and capture native token usage
- Labels: enhancement, important, self-heal (no bug → /implement-feature)
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/324

## resume-detection
- Issue OPEN; no merged PR for Codex Tokens capture; no prior `*-codex-cli-token-usage` spec
- Note: `context/spec/324-whole-document-storage` is a different ticket (#311)

## workspace
- BRANCH: feat/324-codex-cli-token-usage
- WT: .claude/worktrees/feat-324-codex-cli-token-usage
- TMP_VAULT: $WT/.worktree-vault
- Base: origin/main @ 9078f12 (includes #325 session-tokens store)

## specs
- SPEC_NAME: 329-codex-cli-token-usage
- functional-spec.md: Approved (reasoning omitted from Tokens when separable)
- technical-considerations.md: Approved
- tasks.md: written (5 slices; draft-approve suppressed per implement-feature)

## commit-specs
- Commit: 5bba2fa docs: add spec for #324 Codex CLI token usage

## implement
- Slices 1–5 complete (mapper, adapter, convert/coverage, docs, full suite)
- Verify: ruff clean; pytest tests/ exit 0 (~287s)
- User smoke confirm: lgtm (Codex measured on live Analytics)

## local-review
- Review file: context/spec/329-codex-cli-token-usage/review.md (session-only)
- Verdict: Comment; Blockers 0; Nits 4
- Keep/drop: keep all (user chose 1)
- Applied: drop context/ link in adapter docs; last-total→lasts fallback + test; unknown --adapter errors + heal_kb; stage untracked modules at commit

## commit-push
- Issue link keyword: Closes #324 — delivers Codex Tokens capture AC owned by this issue (#322 UI remains separate)
- Next: push + open PR; stop appending to this tracked log after PR opens
