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
- Next: commit-specs → implement
