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

- Amended `functional-spec.md` / `technical-considerations.md` through rev 2; both **Approved**
- Wrote `tasks.md` (7 slices): cov gate → standards/agents → agnix+triage → CLI consolidate → mutation gap report → follow-up issues/CHANGELOG → Feature Testing
- Next: commit specs → `/awos:implement`

## implement — slices 1–4 done; slice 5 maintainer gate

- Specs already committed (`6baa4c2`). Uncommitted: cov gate, CODING_STANDARDS, testing-expert symlink, agnix, CLI consolidations, mutation notes.
- Slice 4: deleted 27 dead “subcommand removed” tests; CLI unit tests now under `tests/cli/` (86 tests); coverage still 87.33%; ruff green.
- Slice 5: mutmut 3.8 stalled (~154MB trampoline on `cli.py`); custom AST sample 20 killed / 16 survived of 36 executed. Report: `context/spec/280-shrink-test-suite/mutation-experiment.md`. Modest CLI-handler guardrail in CODING_STANDARDS + testing-expert. No tests written from survivors.
- Agnix REF-001 filed upstream as [agent-sh/agnix#1629](https://github.com/agent-sh/agnix/issues/1629) (generic plugin paths).
- Next: maintainer choice on mutation follow-up, then slice 6 (follow-up issues + CHANGELOG) and slice 7 (testing-expert).

## implement — slice 6 (follow-up issues + CHANGELOG)

- Filed [#314](https://github.com/AlexanderMakarov/llm-wiki/issues/314) scoped mutation (important); layout migrations [#315](https://github.com/AlexanderMakarov/llm-wiki/issues/315) render, [#316](https://github.com/AlexanderMakarov/llm-wiki/issues/316) MCP, [#317](https://github.com/AlexanderMakarov/llm-wiki/issues/317) adapters, [#318](https://github.com/AlexanderMakarov/llm-wiki/issues/318) synth (minor/self-heal). Skipped dup: #271 is coverage visibility only, not layout/mutation.
- CHANGELOG Unreleased: #280 coverage 87%, CODING_STANDARDS, CLI `tests/cli/`, testing-expert, agnix, mutation spec pointer.
- Next: slice 7 (testing-expert / feature testing).

## implement — slice 7 + verify

- Slice 7: gate invariants in `tests/test_quality_gates.py`; unit cov still 87.33%.
- `/awos:verify`: 22/22 functional ACs marked; spec + tech Status **Completed**. No visual/UI criteria. Roadmap has no #280 row (GH issue is the roadmap item). Optional later: `/awos:architecture` to declare pytest as the testing stack (hired-agents already notes the gap).
- Next: operator smoke confirm, then local review keep/drop (Step 8). Do not push until then.

## verify — local tests + mutmut redo

- `pytest tests/cli/` + gate tests: pass. Full unit `--cov=llmwiki`: **87.33%**, exit 0 (~5.5 min).
- mutmut 3 docs: trampoline model; `cli.py` too large. Successful run on `llmwiki/tag_utils.py`: 54 mutants, 38 killed, 16 survived (~7s). Recipe in `mutation-experiment.md`. Throwaway `setup.cfg` / `mutants/` removed.
- Duplicate CLI-handler row in `.claude/agents/testing-expert.md` removed.
- Next: user still owns smoke/review keep/drop before push.

## correction — synth proof batch (guardrails + mutmut in #280)

- Line coverage 87% ≠ mutation kill rate. tag_utils 16/54 survivors was weak asserts, not 70% line coverage.
- `tests/cli/test_synth.py`: `cmd_synthesize` contracts (handler mutex, harvest rc, unavailable backend, `--backend` disk isolation, sources-only summary).
- `tests/synth/test_reporting.py` mirrors `llmwiki/synth/reporting.py`. mutmut 3.8: 66/66 killed after tightening exact strings and default kwargs.
- Removed `tests/cli/test_synth_backend.py` and `tests/test_synth_rename.py` (duplicates). CLI overlay tests left `test_synth_backends_shared.py`.
- #314 retargeted as expansion only. CODING_STANDARDS: proof-batch mutmut belongs in this change.

## local-review — keep/drop applied (pre-commit)

- Smoke: operator proceeded with delivery. Live vault not mutated.
- Review: `context/spec/280-shrink-test-suite/review.md` (session-only). Verdict Request changes: 3 blockers, 5 nits.
- Keep/drop: keep all. Extra: do not commit mutation sample script/results (belong to #314); N5 CHANGELOG gaps explained then applied.
- Applied: B1 uninstrumented `-m slow` CI step + docs; B2 in-process `cmd_sync` spy + argv smoke; B3 deleted `run_cli_mutation_sample.py` and sample dumps; N1 `tests/test_quality_gates.py`; N2 content asserts; N3 restore `--vault` rationale; N4 drop inert `[files].exclude`; N5 CHANGELOG `addopts` + PyPI `build`.
- Next: static gate, commit, rebase, PR, wait CI. Do not merge without explicit yes.
