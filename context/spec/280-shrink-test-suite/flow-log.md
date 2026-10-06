# Flow log: 280-shrink-test-suite

## fetch-ticket / resume-detection / workspace

- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/280 (enhancement, important, self-heal — no `bug` → `/implement-feature`)
- Branch: `feat/280-shrink-test-suite`
- Worktree: `.claude/worktrees/feat-280-shrink-test-suite` + throwaway `.worktree-vault`
- Parked material noted: `docs/280-test-coverage-rule` @ `1772caa` (CONTRIBUTING Testing guideline draft)
- Measured baseline (worktree, pytest `--cov=llmwiki`, ignore e2e): ~87.33% line coverage (18849/21583 stmts); ~238s wall-time baseline cited in ticket
- Next: specs

## specs — functional-spec approved

- Spec dir: `context/spec/280-shrink-test-suite/` (renamed from auto `305-shrink-test-suite` to match issue)
- Wrote `functional-spec.md` (Status: Approved) after iterative clarifications: gates are primary delivery; proofs secondary; coverage CI ≥80%; staged mutation; agnix for resulting skills/rules; no count-based CI gate; behavior-preserving proofs only
- Next: `/awos:tech` (approval gate)

## specs — functional amended + technical draft (rev 2)

- Coverage gate: **unit-only** 87% (confirmed)
- Mutation: measure what guardrails miss; tune guardrails modestly; **do not** write all missing tests from survivors; present results and ask file-important-issue vs skip
- Agnix: first-run important findings → ask fix-in-PR vs postpone GH issues
- Next: tech approval gate

- Amended `functional-spec.md`: fail_under **87%**; dead-skip cleanup; testing-expert (not `/awos:flow` regen); #290 agnix kit CI in scope; mirror `llmwiki/` under `tests/` by consolidating into package modules (no one-module-per-feature); first PR = gates+proofs; follow-up GH issues per area; usefulness = one-sentence test docstring (not PR coverage essay); TDD guidance only
- Drafted `technical-considerations.md` (Status: Draft) — awaiting tech approval
- Next: user approve tech → `/awos:tasks` (no blocking Approve under `/implement-feature`)
