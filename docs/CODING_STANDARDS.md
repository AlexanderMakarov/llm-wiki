# Coding standards — tests and quality (agent-facing)

Human contributors: start with [`CONTRIBUTING.md`](../CONTRIBUTING.md) §Testing for commands and PR expectations. This document is the canonical detail for agents and maintainers working on `llmwiki/` and `tests/`.

## Principles

**Usefulness beats count.** Fewer tests that each guard real behaviour are better than a large suite of duplicates, vacuous asserts, and files that only exist to bump a number. When you touch an area, prefer consolidating and strengthening tests over adding another root-level module.

**Unit coverage floor.** CI gates the default unit invocation (`pytest tests/` with `tests/e2e` ignored and `@pytest.mark.slow` deselected via `pyproject.toml` `addopts`) at **≥87%** line coverage on `llmwiki` (`[tool.coverage.report] fail_under = 87`). Do not merge changes that drop below the floor without restoring meaningful tests—not filler written only to satisfy the gate.

**Mirror `tests/` to `llmwiki/`.** New and consolidated tests should live under a layout that reflects product code (e.g. `tests/cli/` for CLI-focused tests, packages aligned with `llmwiki/` subpackages). Do not add new **one-module-per-feature** sprawl at `tests/test_<feature>.py` when an existing mirrored module can absorb the cases.

**No new `test_<digits>_*.py` filenames.** Use a stable feature or module slug; link issues and AWOS specs in the module docstring and/or `# @spec:` comments. Legacy `test_<digits>_…` files remain until migrated.

**One-sentence behaviour docstring per test function.** State what user-visible or contract behaviour must hold if the test passes (not “test foo” or restating the function name). Module docstrings can carry broader context and `@spec` links.

**Weak-test patterns.** Avoid asserts and structure that pass without proving the code under test did the work. Review the [PIT weak tests catalogue](https://pitest.org/weak_tests/) when writing or reviewing tests—e.g. asserts on constants only, tautologies, tests that never reach the branch they claim to cover, or assertions that duplicate the implementation.

**CLI handlers (consolidation batches).** For `cmd_*` entrypoints, a test should drive the handler with representative argv (or call the handler after `parse_args`) and assert **exit code plus at least one distinctive stdout/stderr fragment or filesystem side effect** on the path under test. Parser-only checks (`build_parser` subcommand exists, help smoke) and tests that mock away everything after `parse_args` are fine as supplements, not as the only guard for post-parse branches (auto-build/reindex, search bulk footers, synth flag mutual-exclusion, harvest return codes).

**No wall-clock timing outside deliberate slow/perf tests.** Do not assert on elapsed time, `time.sleep`, or race-prone timing in the fast unit suite. Performance and timing belong in `@pytest.mark.slow` tests (`tests/test_lint_perf.py`); the default unit run deselects them, and CI re-runs them uninstrumented after the coverage step.

**Isolation.** Respect suite fixtures in `tests/conftest.py` (vault isolation, neutralized repo-root `config.json`). Tests that need the real user-config overlay must monkeypatch `_USER_CONFIG` / `USER_CONFIG_FILE` themselves. Do not leak state between tests.

**Behavior-preserving cleanups.** Deleting a test, merging modules, or removing a skip is fine when behaviour is unchanged or the old test no longer describes reality—say so in the PR. Do not leave rotting duplicates beside replacements.

**TDD encouraged.** For new behaviour, writing the failing test first is welcome when it clarifies the contract; it is not mandatory for every change.

## Before adding a test

Search for existing coverage and extend it when possible:

```bash
grep -rn "<symbol-or-filename>" tests/
python3 -m pytest tests/ -q -k "<keyword>"
```

A test for a new rule must **fail when that rule is removed**. A test that can pass on an empty input or only through another code path is not covering what you think it is.

## Skips

| Kind | Action |
|---|---|
| `@pytest.mark.skip(reason="… subcommand removed")` (dead product surface) | **Delete** the skip and the test if the surface is gone; do not keep zombie skips. |
| Env / optional-tool skips (missing binary, OS-only) | Keep when justified; document why in the skip reason or nearby comment. |
| Empty-input skips that go green without exercising code | Delete or rewrite when you touch that file. |

## Local batches and mutation (gap measurement)

**Line coverage vs mutation score.** The 87% CI gate is **line** coverage: the fraction of `llmwiki` statements that ran. Mutation score is different: the fraction of tiny synthetic bugs the suite **fails on**. A module can be at 100% line coverage and still have survivors (weak asserts). Do not treat “16 of 54 mutants survived” as “line coverage is 70%.”

**Proof batch in this change.** For the scoped module under test (`llmwiki/synth/reporting.py` plus `llmwiki synth` handler tests), run mutmut on that module, then **strengthen tests until survivors are gone or explained as equivalent mutants**. Do not park that proof on a follow-up issue. Broader mutation of other packages remains a later, scoped run — not a substitute for the proof batch.

## Related

- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — human-facing workflow, exact pytest/coverage/e2e commands, adapter test requirements.
- `.claude/agents/testing-expert.md` — agent specialization for test work (updated in the #280 series).
