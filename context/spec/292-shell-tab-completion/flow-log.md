# Flow log — #294 shell TAB completion

## specs
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/294
- Branch `feat/294-shell-completion`, worktree `.claude/worktrees/feat-294-shell-completion`, throwaway vault `.worktree-vault/`.
- functional-spec.md + technical-considerations.md approved by user; tasks.md written (4 slices, no draft gate).
- Decisions: commands only; shell builtins only (bash `complete -F`, zsh `compdef`); no generator subcommand/script file; setup.sh asks [Y/n], edits login shell rc, refreshes marker line on re-run; skip via `LLMWIKI_SKIP_COMPLETION=1`.
- Next: implement (`/awos:implement`).
