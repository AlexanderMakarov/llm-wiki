---
name: contributing-rules
load: always
applies_to: "**/*"
---

# Contributing rules (always loaded)

[`CONTRIBUTING.md`](../../CONTRIBUTING.md) at the repo root is the **single
authoritative source** for how to contribute to llmwiki. Read it before shipping
a PR. This file deliberately stays a thin pointer — an earlier version restated
the rules and drifted out of sync with them, which is worse than not restating
them at all. Add process rules to `CONTRIBUTING.md`, never here.

## The short version

1. **One concern per PR**, ≤500 lines of diff. A mechanical, generated diff may
   exceed that if the PR body says so and states that behaviour is unchanged.
2. **Conventional-commit titles**, using only the types CONTRIBUTING lists:
   `feat` `fix` `chore` `docs` `test` `refactor` `perf` `security` `release`.
   Link the issue with `Closes #N`.
3. **Docs + `CHANGELOG.md` under `## [Unreleased]`** for every user-visible
   change. New CLI subcommands, config keys, and lint rules also need their row
   in `docs/reference/*.md` in the same PR.
4. **No new runtime dependencies.** Stdlib plus `markdown` only.
5. **No AI attribution trailers** (`Co-authored-by: Claude` and similar).
   Commits are human-authored. Use your own git identity on your own fork.
6. **Never push to the default branch.** Open a PR; CI must pass before merge.
7. **No scope creep and no silent refactors.** Found something else broken? File
   an issue. Renaming something? Say so in the PR title.
8. **Privacy is non-negotiable.** No real session data — fixtures are synthetic
   or heavily redacted. No machine-specific paths, usernames, hostnames, or
   vault roots in code, tests, commits, PR bodies, or the CHANGELOG; use
   placeholders such as `/home/USER/…`, `<vault>`, `<user>`.

## Before pushing

```bash
ruff check llmwiki tests scripts   # lint
python3 -m pytest tests/ -q        # tests
```

The committed `pre-push` hook in `.githooks/` lints the Python files in your
push and rejects it on violations. `./setup.sh` wires it; enable it manually
with `git config core.hooksPath .githooks`.

## Not to be confused with the vault schema

`CLAUDE.md` and `AGENTS.md` at the repo root describe how an agent maintains a
**user's** `raw/` → `wiki/` → `site/` knowledge base. They are the product's
schema, not rules for developing llmwiki itself.
