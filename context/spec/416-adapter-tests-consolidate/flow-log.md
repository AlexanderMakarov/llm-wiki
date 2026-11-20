# Flow log: 416-adapter-tests-consolidate (#317)

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/317 — test: consolidate adapter tests under tests/adapters/
- Labels: enhancement, minor, self-heal
- Open; no existing PR for #317

## resume-detection
- No prior 317/416 spec artifacts; start from workspace

## workspace
- BRANCH=`feat/317-adapter-tests-layout`
- WT=`<repo>/.claude/worktrees/feat-317-adapter-tests-layout`
- MAIN=`<repo>`
- TMP_VAULT=`$WT/.worktree-vault`

## specs
- functional-spec.md: Approved (user; batch option 1 — unit + shared contracts)
- technical-considerations.md: Approved (user pre-approved with functional)
- tasks.md: drafted (informational; no draft Approve ask under /implement-feature)
- SPEC_NAME=`416-adapter-tests-consolidate`
- Next: commit-specs

## commit-specs
- Commit on BRANCH — docs: add spec for #317 consolidate adapter tests under tests/adapters/
- Next: implement

## implement (Slices 1–3)
- Moved §2.1 batch into `tests/adapters/` (+ `contrib/`); no `__init__.py` (#316 convention).
- Hygiene: dropped vacuous Cursor `session_store_path` tautology in graduation; removed dead `if False` Path write in chatgpt render test; one-sentence docstrings + `@spec: 416` on batch modules.
- Updated CODING_STANDARDS, quality-gate layout checks, adapter docs paths, CHANGELOG Unreleased #280/#315/#316 bullets → include #317 / `tests/adapters/`.
- Stay-put modules left flat; Slice 4 left for testing-expert.

## testing (Slice 4)
- Reviewed functional-spec ACs: Slices 1–3 already gated dir layout, contrib layout, no-init, CODING_STANDARDS mention, 230 adapters tests passing.
- Added two new gates to `tests/test_quality_gates.py` for unguarded ACs: `test_adapter_tests_all_have_behaviour_docstrings` (AC 2.3 — walks AST of all test functions in `tests/adapters/**`, fails on any missing docstring) and `test_flat_batch_originals_removed_from_tests_root` (migration completeness — asserts the 14 §2.1 flat originals are absent from `tests/`).
- Also added `# @spec: 416-adapter-tests-consolidate` and `import ast` to the module header.
- RED validation: gate logic confirmed with an injected undocstring'd test function; flat-originals gate confirmed absent → would fail on re-introduction.
- Final: `ruff check` clean; 21 quality gates + 230 adapter tests → 251 passed, 1 skipped.

## verify
- Functional + technical Status → Completed; ACs checked with layout/gates/suite/cov/contract evidence
- ruff clean; pytest tests/adapters/ + quality_gates green; full suite 6813 passed earlier; coverage 87.33%
- Next: local-review (smoke confirm first)

## local-review
- Smoke: agent-run ruff + pytest tests/adapters/ + quality_gates + live lint (exit 0); user asked agent to run smoke
- Review file: context/spec/416-adapter-tests-consolidate/review.md
- Verdict: Request changes; Blockers 1; Nits 3
- Next: dedicated keep/drop ask (stop turn)

## local-review keep/drop
- User chose: keep all findings (B1 + N1–N3)
- Applied: delete flat-inventory + docstring AST gates; strip echo docstrings; CONTRIBUTING adapter test path; merge `# @spec: … (#317)`; tasks.md drop optional flat-originals wording
- Next: static gate then commit-push

## commit-push
- Issue link keyword: `Closes #317` — issue owns only the adapter unit-test mirror pass; acceptance/watch/docs-currency stay put; synth mirrors are other tickets
- Staging: implementation + docs + AWOS notes; exclude `review.md` / vault / config
- Last committed flow-log state before PR open
- Static gate after keep/drop: ruff clean; full pytest exit 0
