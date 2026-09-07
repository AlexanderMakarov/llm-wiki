# Flow log: 226-cursor-cli-synth-backend (#230)

## fetch-ticket / resume-detection / workspace

- Ticket: [#230](https://github.com/AlexanderMakarov/llm-wiki/issues/230) — feat: Cursor Agent CLI synthesis backend (OPEN; no merged PR for same work; PR #231 is unrelated path-scoped synth).
- Branch: `feat/230-cursor-cli-synth-backend`
- Worktree: `.claude/worktrees/feat-230-cursor-cli-synth-backend`
- Throwaway vault: worktree `.worktree-vault` via worktree `config.json`
- Next: specs

## specs — functional-spec

- Wrote and user-approved `functional-spec.md` (Author: Aleksandr Makarov).
- Later amended on tech feedback: nested `synthesis.claude` / `cursor_cli` / `ollama`; default Composer model; no path key; lean = print + ask + sandbox; overview follows backend (dummy spends nothing); rate card Cursor rows.
- Next: tech

## specs — technical-considerations

- User-approved `technical-considerations.md`.
- Next: tasks

## specs — tasks

- Wrote `tasks.md` (6 slices; coding → `general-purpose`; QA → `testing-expert`). Informational summary only — no draft Approve gate under `/implement-feature`.
- Next: commit-specs then `/awos:implement`
