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

**No wall-clock timing outside deliberate slow/perf tests.** Do not assert on elapsed time, `time.sleep`, or race-prone timing in the fast unit suite. Performance and timing belong in `@pytest.mark.slow` tests (`tests/test_lint_perf.py`); the default unit run deselects them, and the `performance-budget` job in CI runs them without coverage.

**Isolation.** Every test runs in its own settings sandbox: a throwaway home directory and operator `config.json`. Prepare and inspect settings through the `settings_sandbox` fixture (`write_operator`, `read_operator`, `home`, `xdg_state`); never patch settings paths or `HOME` in a test. Product code resolves every settings location when it is used, through one accessor such as `config_schedule.user_config_path()` or `Path.home()`, never through a module-level path constant, so the sandbox reaches it. Every pytest run fails when it changed a tracked file, the repo-root `config.json`, or llmwiki's settings under the real home directory; to find the test, run that run's modules one at a time. Do not leak state between tests.

**Share expensive setup through scoped fixtures.** When several tests need the same expensive setup — a built site, a seeded vault, a git repository, a CLI subprocess run — build it once in a `scope="module"` (or `"session"`) fixture and let each test assert on the result, instead of rebuilding it in every test. Tests that share a scoped fixture treat it as read-only; a test that changes the setup builds its own function-scoped copy. Never merge separate behaviours into one test to save time: each test still states one behaviour, and the shared fixture is what saves the time.

**Behavior-preserving cleanups.** Deleting a test, merging modules, or removing a skip is fine when behaviour is unchanged or the old test no longer describes reality—say so in the PR. Do not leave rotting duplicates beside replacements.

**When the behaviour is not on disk yet.** Write the test so it fails for that missing behaviour, then implement until it passes. Do not start with a passing test for an unimplemented contract.

**When the behaviour already ships.** Cover or consolidate it with assertions that would fail if it broke. Do not invent a failing-test cycle for already-green code.

## Before adding a test

Search for existing coverage and extend it when possible:

```bash
grep -rn "<symbol-or-filename>" tests/
python3 -m pytest tests/ -q -k "<keyword>"
```

A test for a new rule must **fail when that rule is removed**. A test that can pass on an empty input or only through another code path is not covering what you think it is.

Three failure modes seen in this repo:

1. **The duplicate.** Two tests asserting the same contract drift apart. Extend the existing test — a new parametrize case usually beats a new function.
2. **The test that exercises nothing.** A case can pass entirely through some other code path. Check by removing the rule: if the test still passes, it is not covering it.
3. **The test that asserts over an empty input.** If a test can pass on an empty corpus, it is not covering the corpus.

## Skips

| Kind | Action |
|---|---|
| Skip whose reason is a removed product surface | Do not add zombie skips. If you find one, delete it. |
| Env / optional-tool skips (missing binary, OS-only) | Keep when justified; document why in the skip reason or nearby comment. |
| Empty-input skips that go green without exercising code | Delete or rewrite when you touch that file. |

## Line coverage vs mutation (gap measurement)

**Line coverage vs mutation score.** The 87% CI gate is **line** coverage: the fraction of `llmwiki` statements that ran. Mutation score is different: the fraction of tiny synthetic bugs a suite **fails on**. A module can be at 100% line coverage and still have survivors (weak asserts). Do not treat “16 of 54 mutants survived” as “line coverage is 70%.”

**No mutation harness.** The repo commits no mutation-testing harness and CI runs no mutation job. A one-off local mutation run is a fine way to find weak tests in one module; what lands is stronger ordinary pytest assertions, never the harness.

## Related

- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — human-facing workflow, exact pytest/coverage/e2e commands, adapter test requirements.
- `.claude/agents/testing-expert.md` — AWOS QA agent; this repo’s layout and usefulness rules are patched into its existing steps, not a sidecar section.
