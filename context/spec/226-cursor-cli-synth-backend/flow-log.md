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

## commit-specs

- Commit `ea71f23` — docs: add spec for #230
- Next: implement

## local-review

- Review file: `context/spec/226-cursor-cli-synth-backend/review.md` (session-only, not to be committed)
- Verdict: Request changes — Blockers 1, Nits 1
- Next: user keep/drop, then apply accepted findings before push


## implement — Slice 5 (pricing + docs)

- Extended `llmwiki/model_pricing.csv` with Cursor-published Composer 2.5 / Grok 4.5 / 4.6 (+ Fast) rates and `agent --model` aliases (cache_write=input where Cursor lists no separate write fee). No Kimi K3 stand-in needed for those ids.
- Docs + CHANGELOG / UPGRADING / install-automation backend prompt; distinguish synth backend vs ingest adapters.
- Pricing alias resolution tests; Slice 5 marked done in `tasks.md`.
- Next: Slice 6 (feature testing / regression).

## commit-push

- Applied review keep: B1 (prepend stable prefix + regression test; corrected cache docs) and N1 (public `run_prompt` DRY).
- Local review file remains gitignored / unstaged.
- Next: push + open PR; stop appending flow-log after PR opens.

## post-PR lean allowlist

- Live-probed hidden Agent CLI flags on `composer-2.5`: `--system-prompt` / `--exclude-workspace-context` rejected for this account; `--allowed-tools truncated_tool_call` cuts prompt ~30k → ~21k.
- Wired tiny allowlist into `lean_argv`; docs + CHANGELOG + tests updated.

## refactor — shared overview + tests + config rows

- Collapsed nested/legacy Claude rows in `configuration-reference.md`.
- Replaced `_overview_via_*` with `BaseSynthesizer.overview_completion` on Claude / Cursor / Ollama.
- Added `tests/test_synth_backends_shared.py` (parametrize resolve/CLI/overview); trimmed Cursor acceptance + backend CLI dupes; moved Claude nested-config tests into `test_synth_claude_cli.py`.
- Next: local review.
