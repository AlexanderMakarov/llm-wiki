---
paths:
  - "llmwiki/**"
  - "tests/**"
  - "scripts/**"
  - "docs/**"
  - "integrations/**"
  - ".github/**"
  - ".githooks/**"
  - "pyproject.toml"
  - "CHANGELOG.md"
  - "CONTRIBUTING.md"
  - "README.md"
  - "setup.sh"
  - "setup.bat"
---

# Contributing to llmwiki (repo code work)

You are changing **this repository's own code or docs**, not a user's vault. [`CONTRIBUTING.md`](../../CONTRIBUTING.md) is authoritative — read it before you ship a PR, and re-read it when starting new work rather than trusting a memory of it from an earlier turn. What follows is the short version.

## Do not confuse the vault schema with the contribution guide

[`CLAUDE.md`](../../CLAUDE.md) and [`AGENTS.md`](../../AGENTS.md) at the repo root describe how an agent maintains a **user's knowledge vault** (`raw/` → `wiki/` → `site/`). They are the product's schema, not rules for developing llmwiki itself. Never put repo, PR, or process rules into them, and never apply their vault workflows to a code change.

## Non-negotiables

1. **One concern per PR.** No mixing a bug fix with a feature.
2. **Conventional-commit titles**, using only the types in CONTRIBUTING's table: `feat` `fix` `chore` `docs` `test` `refactor` `perf` `security` `release`. Link the issue with `Closes #N` only when the PR fully completes it; otherwise `Relevant to #N`. Completeness is judged against what the issue itself owns — work it hands to another issue does not count.
3. **Every user-visible change ships docs + a `CHANGELOG.md` entry** under `## [Unreleased]`. If the thing you change is itself still unreleased (it only appears under `[Unreleased]`), update that existing entry to the final behaviour instead of adding a *Fixed* / *Changed* entry for it. A new CLI subcommand, slash command, config key, or lint rule also needs its row in `docs/reference/*.md` in the same PR — CI enforces the CLI coverage check.
4. **No new runtime dependencies.** Stdlib plus `markdown` only.
5. **No real session data and no personal machine details.** Fixtures are synthetic or heavily redacted. Absolute home paths, OS usernames, hostnames, and vault roots stay out of code, tests, commits, PR bodies, and the CHANGELOG — use placeholders like `/home/USER/…`, `<vault>`, `<user>`.
6. **Verify before fixing an old issue.** Reproduce it on the current default branch first; if it no longer reproduces, close it with the resolving commit instead of shipping a speculative fix.
7. **Never fail silently in the browser.** Runtime failures in the generated site must surface on the page via `window.__llmwikiReportError`, not just in the console. See CONTRIBUTING's *Static-site error handling* section.
8. **No GitHub issue numbers in new test filenames.** Prefer a stable feature/module slug (`tests/test_unified_document_pages_acceptance.py`, not `tests/test_305_….py`). Link the issue or AWOS spec in the module docstring and/or `# @spec:` comments. Existing `test_<digits>_…` files are legacy; do not add new ones (full rule: [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md)).
9. **Check for existing test coverage before adding a test.** Search `tests/` and extend what is there rather than adding beside it. A test for a new rule must fail when that rule is removed — if it still passes, it is exercising a different code path — and a test that can pass over an empty input covers nothing. Canonical detail: [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md).

## Markdown formatting

**Never hard-wrap prose at a fixed column.** One paragraph is one line, however long. Line width is the renderer's job, not the file's.

## Before you push

Run both, from the repo root:

```bash
ruff check llmwiki tests scripts   # lint
python3 -m pytest tests/ -q        # tests
```

A committed `pre-push` hook in `.githooks/` lints the Python files in your push and rejects it on violations. It is wired by `./setup.sh`; enable it manually with:

```bash
git config core.hooksPath .githooks
```

Prefer `ruff check --fix --select …` for safe rule families — never bare `ruff check --fix` (it can delete deliberate re-exports). If you must bypass the hook, `git push --no-verify` works, but say why in the PR.

## After you push — wait for CI

Local green is not enough. After every `git push` that creates or updates a PR, **wait for GitHub Actions on that head SHA**, report green/red to the user, and if anything failed: read logs (`gh run view <id> --log-failed`), fix, push, wait again. Prefer `gh pr checks <n> --watch`. Do not call the PR ready while required checks are pending (unless the user says not to wait). Full detail: CONTRIBUTING *After you push*.

## PR checklist boxes

When writing or updating a PR body, include only the Pre-merge checks that apply to *this* PR — not a fixed dump of the template. Mark `- [x]` for what you verified this session (or N/A with a one-line waiver). Leave `- [ ]` only for what you cannot verify yourself. When new evidence arrives (e.g. CI goes green), update the PR body (`gh pr edit`).

## Python conventions

- Imports belong at the top of the module. Deferring one inside a function is acceptable **only** for an optional extra (`trafilatura`, `markitdown`, `graphifyy`, `networkx`) or to break a proven import cycle — and the reason goes in a `# noqa: PLC0415` comment on the line. Stdlib is never deferred. `PLC0415` is enforced everywhere except `scripts/**`.
- Prefer importing helpers from the owning module over high-level facade re-exports.
- Public functions carry a docstring. Short is fine; absent is not.
- Remove dead code, unused imports, and unused variables as you go.
