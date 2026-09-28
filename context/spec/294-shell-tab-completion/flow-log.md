# Flow log — #294 shell TAB completion

## specs
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/294
- Branch `feat/294-shell-completion`, worktree `.claude/worktrees/feat-294-shell-completion`, throwaway vault `.worktree-vault/`.
- functional-spec.md + technical-considerations.md approved by user; tasks.md written (4 slices, no draft gate).
- Decisions: commands only; shell builtins only (bash `complete -F`, zsh `compdef`); no generator subcommand/script file; setup.sh asks [Y/n], edits login shell rc, refreshes marker line on re-run; skip via `LLMWIKI_SKIP_COMPLETION=1`.
- Next: implement (`/awos:implement`).

## implement + verify
- Slices 1–3 (general-purpose) and Slice 4 (testing-expert) done; tasks.md all [x].
- New: llmwiki/shell_completion.py, scripts/setup-completion.sh (sourced setup helper, kept — user did not object), tests/test_shell_completion.py, tests/test_shell_completion_acceptance.py. Changed: setup.sh, docs/getting-started.md, docs/reference/cli.md, CHANGELOG.md.
- 23 feature tests pass, 1 skip (zsh not installed locally); ruff clean; full suite green.
- User smoke-confirmed bash completion.
- Next: local review → context/spec/294-shell-tab-completion/review.md.

## local review + commit-push
- Review file (session-only, not committed): context/spec/294-shell-tab-completion/review.md — verdict Comment, 0 Blockers / 5 Nits.
- User keep/drop: N1 (delete dead llmwiki/completion.py), N2 (macOS bash → ~/.bash_profile), N3 (atomic rc write, surrogateescape, symlink/mode kept), N4 (spec dir 292 → 294) kept; N5 changed per user — all wall-clock timing assertions removed, PTY reads return on match.
- Static gate green (ruff + full pytest). Specs marked Completed.
- Next: push branch, open PR against main, watch CI (log frozen from here).
