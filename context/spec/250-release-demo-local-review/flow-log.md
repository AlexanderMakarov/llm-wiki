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

## specs — tech approved; tasks written (2026-09-14)

- Human accepted revised tech (`lgtm`); Status → Approved
- Wrote `tasks.md`: Slice 1 gate script + tests; Slice 2 thin skill/docs; Slice 3 regression
- Next: commit specs, then implement slices via subagents

## commit-specs (2026-09-14)

- Commit `9c3f8f2` — `docs: add spec for #240 release demo local review gate`
- Next: implement

## implement (2026-09-14)

- Slice 1: `scripts/release_demo_gate.py` + `tests/test_release_demo_gate.py` (8 tests)
- Slice 2: RELEASE_PROCESS + release SKILL thin around gate; REFRESH_DEMO one-liner; CHANGELOG; `test_209` #240 asserts
- Slice 3: targeted + full non-e2e pytest / ruff green
- testing-expert Task hit usage limit — orchestrator finished test/docs slices
- Local verify: dry-run + full gate (usage window → 2026-09-14); CI/wiki-checks mimic green
- Local review: Request changes (B1 uncommitted) — fixed N2 doc order, N3/N4 tests; committing next
- Next: commit-push → PR → remote gates
