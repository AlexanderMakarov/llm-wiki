# Flow log — #240 release demo local review

## workspace (2026-09-12)

- Branch: `feat/240-release-demo-local-review`
- Worktree: `.claude/worktrees/feat-240-release-demo-local-review` (from `origin/main` @ `3b0e154`)
- Throwaway vault: `.worktree-vault` via worktree `config.json`
- Ticket: https://github.com/AlexanderMakarov/llm-wiki/issues/240 (open)
- Prior slice note: #254/#255 already cover committed demo `llmwiki-state` (Home Pipeline); remaining scope is usage regen + local site review gate + checklist/skill alignment
- Next: functional-spec approval gate

## specs — functional-spec drafted (2026-09-12)

- Wrote `context/spec/250-release-demo-local-review/functional-spec.md` (Status: In Review)
- Author: Aleksandr Makarov
- Next: wait for human accept of functional-spec, then `/awos:tech`

## specs — functional approved; tech drafted (2026-09-14)

- Human accepted functional-spec (`lgtm`); Status → Approved
- Wrote `technical-considerations.md` (Status: In Review): docs/skill + `test_209` string locks; reuse `generate_demo_usage.py --today`; no Pages/runtime/#255 redo; align skill “filenames” wording with in-place-by-slug process
- Next: wait for human accept of technical-considerations, then `/awos:tasks`

## specs — tech revised script-first (2026-09-14)

- Human feedback: prefer hard-scriptable release mechanics over LLM skill prose; asked about `/flow` and whether #255 belongs in same PR
- Revised `technical-considerations.md`: add `scripts/release_demo_gate.py` (usage + build + URL print + case-fold; exit codes); skill/RELEASE_PROCESS thin wrappers; #255 still out of this PR
- Next: wait for human accept of revised technical-considerations
